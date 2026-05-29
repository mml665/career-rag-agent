<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listJobs, addJob, deleteJob } from '@/api/jobs'
import { extractJobFile, extractJobText } from '@/api/library'
import type { JobPosting } from '@/api/types'

const jobs = ref<JobPosting[]>([])
const loading = ref(false)
const uploadLoading = ref(false)
const extractLoading = ref(false)

const form = ref({
  company: '', title: '', location: '', source_url: '',
  raw_description: '', required_skills: '', preferred_skills: '', internship_requirements: '',
})

async function loadJobs() {
  try { jobs.value = await listJobs() } catch {}
}
onMounted(loadJobs)

async function handleExtractFromText() {
  if (!form.value.raw_description.trim()) {
    ElMessage.warning('请先输入 JD 文本')
    return
  }
  extractLoading.value = true
  try {
    const r = await extractJobText(form.value.raw_description)
    if (r.company) form.value.company = r.company
    if (r.title) form.value.title = r.title
    if (r.location) form.value.location = r.location
    if (r.required_skills?.length) form.value.required_skills = r.required_skills.join('、')
    if (r.preferred_skills?.length) form.value.preferred_skills = r.preferred_skills.join('、')
    if (r.internship_requirements?.length) form.value.internship_requirements = r.internship_requirements.join('、')
    ElMessage.success('已从 JD 提取字段，请核对后保存')
  } finally { extractLoading.value = false }
}

async function handleUploadJD(file: File) {
  uploadLoading.value = true
  try {
    const r = await extractJobFile(file.name, file)
    if (r.company) form.value.company = r.company
    if (r.title) form.value.title = r.title
    if (r.location) form.value.location = r.location
    if (r.required_skills?.length) form.value.required_skills = r.required_skills.join('、')
    if (r.preferred_skills?.length) form.value.preferred_skills = r.preferred_skills.join('、')
    if (r.internship_requirements?.length) form.value.internship_requirements = r.internship_requirements.join('、')
    ElMessage.success('JD 文件已解析')
  } finally { uploadLoading.value = false }
}

async function handleSave() {
  if (!form.value.company || !form.value.title || !form.value.raw_description) {
    ElMessage.warning('公司、岗位名称和 JD 原文不能为空')
    return
  }
  loading.value = true
  try {
    await addJob({
      company: form.value.company,
      title: form.value.title,
      location: form.value.location,
      source_url: form.value.source_url,
      raw_description: form.value.raw_description,
      required_skills: form.value.required_skills ? form.value.required_skills.split(/[、,，]/).map(s => s.trim()).filter(Boolean) : [],
      preferred_skills: form.value.preferred_skills ? form.value.preferred_skills.split(/[、,，]/).map(s => s.trim()).filter(Boolean) : [],
      internship_requirements: form.value.internship_requirements ? form.value.internship_requirements.split(/[、,，]/).map(s => s.trim()).filter(Boolean) : [],
    })
    ElMessage.success('岗位已保存')
    form.value = { company: '', title: '', location: '', source_url: '', raw_description: '', required_skills: '', preferred_skills: '', internship_requirements: '' }
    await loadJobs()
  } finally { loading.value = false }
}

async function handleDelete(id: string) {
  await deleteJob(id)
  await loadJobs()
  ElMessage.success('岗位已删除')
}
</script>

<template>
  <div class="page-header">
    <h2>岗位库</h2>
    <p>管理岗位 JD，支持上传文件或手动填写</p>
  </div>

  <!-- 上传 JD -->
  <div class="card-section">
    <h3>导入 JD</h3>
    <el-upload
      :auto-upload="false" :show-file-list="false" accept=".pdf,.md,.txt"
      :disabled="uploadLoading"
      @change="(f: any) => f.raw && handleUploadJD(f.raw)"
    >
      <el-button :loading="uploadLoading" type="primary" plain>
        <el-icon><Upload /></el-icon> 上传 JD 文件
      </el-button>
      <template #tip><div class="el-upload__tip">支持 PDF / Markdown / TXT</div></template>
    </el-upload>
  </div>

  <!-- 岗位表单 -->
  <div class="card-section">
    <h3>添加岗位</h3>
    <el-form label-width="100px" @submit.prevent="handleSave">
      <el-row :gutter="16">
        <el-col :span="8"><el-form-item label="公司"><el-input v-model="form.company" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="岗位名称"><el-input v-model="form.title" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="工作地点"><el-input v-model="form.location" /></el-form-item></el-col>
      </el-row>
      <el-form-item label="来源链接"><el-input v-model="form.source_url" placeholder="可选" /></el-form-item>
      <el-form-item label="JD 原文">
        <el-input v-model="form.raw_description" type="textarea" :rows="8" placeholder="粘贴完整 JD..." />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="8"><el-form-item label="必备技能"><el-input v-model="form.required_skills" placeholder="用顿号分隔" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="加分技能"><el-input v-model="form.preferred_skills" placeholder="用顿号分隔" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="实习要求"><el-input v-model="form.internship_requirements" placeholder="用顿号分隔" /></el-form-item></el-col>
      </el-row>
      <el-form-item>
        <el-button :loading="extractLoading" @click="handleExtractFromText">从 JD 提取并回填字段</el-button>
        <el-button type="primary" native-type="submit" :loading="loading">保存岗位</el-button>
      </el-form-item>
    </el-form>
  </div>

  <!-- 已保存岗位 -->
  <div class="card-section" v-if="jobs.length">
    <h3>已保存岗位 ({{ jobs.length }})</h3>
    <el-collapse>
      <el-collapse-item v-for="job in jobs" :key="job.job_id">
        <template #title>
          <div style="flex:1">
            <strong>{{ job.company }} · {{ job.title }}</strong>
            <el-tag size="small" style="margin-left:8px">{{ job.location || '未知' }}</el-tag>
          </div>
        </template>
        <div style="font-size:13px;white-space:pre-wrap;color:var(--color-muted);max-height:200px;overflow-y:auto">{{ job.raw_description }}</div>
        <div v-if="job.required_skills?.length" style="margin-top:8px">
          <el-tag v-for="s in job.required_skills" :key="s" size="small" type="danger" style="margin:2px">{{ s }}</el-tag>
        </div>
        <div v-if="job.preferred_skills?.length" style="margin-top:4px">
          <el-tag v-for="s in job.preferred_skills" :key="s" size="small" type="warning" style="margin:2px">{{ s }}</el-tag>
        </div>
        <div style="margin-top:8px;text-align:right">
          <el-button type="danger" size="small" text @click="handleDelete(job.job_id)">删除岗位</el-button>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>
