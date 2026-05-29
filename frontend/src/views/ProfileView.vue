<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getProfile, saveProfile } from '@/api/profile'
import { listEvidence, saveSections, deleteEvidence } from '@/api/evidence'
import { extractResume } from '@/api/library'
import type { CandidateProfile, ProfileEvidence } from '@/api/types'

const profile = ref<CandidateProfile>({
  name: '', phone: '', email: '', city: '',
  target_role: '', preferred_locations: '', homepage: '', summary: '', updated_at: '',
})

const evidence = ref<ProfileEvidence[]>([])
const loading = ref(false)
const uploadLoading = ref(false)

const draft = ref<Record<string, string>>({
  education: '', skill: '', project: '', award: '', availability: '',
})
const sourceFile = ref('')
const draftVerified = ref(true)

const categoryLabels: Record<string, string> = {
  education: '教育背景', skill: '专业技能', project: '项目经历',
  award: '获奖荣誉', availability: '求职意向',
}

async function loadProfile() {
  try { profile.value = await getProfile() } catch {}
}
async function loadEvidence() {
  try { evidence.value = await listEvidence() } catch {}
}

onMounted(() => { loadProfile(); loadEvidence() })

async function handleSaveProfile() {
  loading.value = true
  try {
    await saveProfile(profile.value)
    ElMessage.success('个人档案已保存')
  } finally { loading.value = false }
}

async function handleSaveEvidence() {
  const sections: Record<string, string> = {}
  for (const [k, v] of Object.entries(draft.value)) {
    if (v.trim()) sections[k] = v.trim()
  }
  if (Object.keys(sections).length === 0) {
    ElMessage.warning('请至少填写一个栏目')
    return
  }
  loading.value = true
  try {
    await saveSections({ sections, source_file: sourceFile.value, verified: draftVerified.value })
    ElMessage.success('履历证据已保存')
    draft.value = { education: '', skill: '', project: '', award: '', availability: '' }
    await loadEvidence()
  } finally { loading.value = false }
}

function loadExistingToDraft() {
  for (const e of evidence.value) {
    if (e.category in draft.value) {
      draft.value[e.category] = e.content
    }
  }
  ElMessage.info('已载入已有履历内容')
}

async function handleUploadResume(file: File) {
  uploadLoading.value = true
  try {
    const result = await extractResume(file.name, file)
    profile.value.name = result.name || profile.value.name
    profile.value.phone = result.phone || profile.value.phone
    profile.value.email = result.email || profile.value.email
    profile.value.city = result.city || profile.value.city
    profile.value.target_role = result.target_role || profile.value.target_role
    profile.value.preferred_locations = result.preferred_locations || profile.value.preferred_locations
    profile.value.homepage = result.homepage || profile.value.homepage
    profile.value.summary = result.summary || profile.value.summary
    draft.value.education = result.education || ''
    draft.value.skill = result.skill || ''
    draft.value.project = result.project || ''
    draft.value.award = result.award || ''
    draft.value.availability = result.availability || ''
    ElMessage.success('简历已解析，请核对后保存')
  } finally { uploadLoading.value = false }
}

async function handleDeleteEvidence(id: string) {
  await deleteEvidence(id)
  await loadEvidence()
}
</script>

<template>
  <div class="page-header">
    <h2>个人档案</h2>
    <p>管理基本信息和已确认的履历证据</p>
  </div>

  <!-- 简历上传 -->
  <div class="card-section">
    <h3>导入简历</h3>
    <el-upload
      :auto-upload="false"
      :show-file-list="false"
      accept=".pdf,.md,.txt"
      :disabled="uploadLoading"
      @change="(f: any) => f.raw && handleUploadResume(f.raw)"
    >
      <el-button :loading="uploadLoading" type="primary" plain>
        <el-icon><Upload /></el-icon> 上传简历自动解析
      </el-button>
      <template #tip>
        <div class="el-upload__tip">支持 PDF / Markdown / TXT</div>
      </template>
    </el-upload>
  </div>

  <!-- 基本信息 -->
  <div class="card-section">
    <h3>基本信息</h3>
    <el-form label-width="90px" @submit.prevent="handleSaveProfile">
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="姓名"><el-input v-model="profile.name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="手机号"><el-input v-model="profile.phone" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="邮箱"><el-input v-model="profile.email" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="城市"><el-input v-model="profile.city" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="求职意向"><el-input v-model="profile.target_role" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="期望地点"><el-input v-model="profile.preferred_locations" /></el-form-item></el-col>
      </el-row>
      <el-form-item label="个人主页"><el-input v-model="profile.homepage" placeholder="GitHub / 作品集链接" /></el-form-item>
      <el-form-item label="个人简介"><el-input v-model="profile.summary" type="textarea" :rows="3" /></el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading">保存基本信息</el-button>
      </el-form-item>
    </el-form>
  </div>

  <!-- 履历证据 -->
  <div class="card-section">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h3 style="margin:0">履历证据</h3>
      <div>
        <el-button size="small" @click="loadExistingToDraft">载入已有履历</el-button>
        <el-button size="small" @click="draft = { education: '', skill: '', project: '', award: '', availability: '' }">清空输入</el-button>
      </div>
    </div>
    <el-form label-width="90px" @submit.prevent="handleSaveEvidence">
      <el-form-item v-for="(label, key) in categoryLabels" :key="key" :label="label">
        <el-input v-model="draft[key]" type="textarea" :rows="3" :placeholder="`输入${label}内容`" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="来源文件"><el-input v-model="sourceFile" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="已确认"><el-switch v-model="draftVerified" /></el-form-item></el-col>
      </el-row>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading">保存履历证据</el-button>
      </el-form-item>
    </el-form>
  </div>

  <!-- 已保存证据 -->
  <div class="card-section" v-if="evidence.length">
    <h3>已保存履历内容</h3>
    <div v-for="e in evidence" :key="e.evidence_id" style="padding:8px 0;border-bottom:1px solid var(--color-border)">
      <div style="display:flex;justify-content:space-between;align-items:start">
        <div>
          <el-tag size="small" type="info">{{ categoryLabels[e.category] || e.category }}</el-tag>
          <el-tag v-if="e.verified" size="small" type="success" style="margin-left:4px">已确认</el-tag>
          <span v-if="e.title" style="margin-left:8px;font-weight:500">{{ e.title }}</span>
          <p style="margin:4px 0 0;font-size:13px;color:var(--color-muted);white-space:pre-wrap">{{ e.content }}</p>
        </div>
        <el-button type="danger" size="small" text @click="handleDeleteEvidence(e.evidence_id)">删除</el-button>
      </div>
    </div>
  </div>
</template>
