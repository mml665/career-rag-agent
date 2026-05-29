<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listJobs } from '@/api/jobs'
import { listEvidence } from '@/api/evidence'
import { tailorResume, exportResume } from '@/api/library'
import { listResumeVersions, addResumeVersion, deleteResumeVersion } from '@/api/resume'
import type { JobPosting, ProfileEvidence, ResumeVersion, TailorResult } from '@/api/types'

const jobs = ref<JobPosting[]>([])
const evidence = ref<ProfileEvidence[]>([])
const versions = ref<ResumeVersion[]>([])
const selectedJobId = ref('')
const selectedEvidenceIds = ref<string[]>([])
const currentText = ref('')
const requestGoal = ref('')
const loading = ref(false)

const tailorResult = ref<TailorResult | null>(null)
const saveName = ref('')
const saveCategory = ref('project')

const categoryLabels: Record<string, string> = {
  education: '教育背景', skill: '专业技能', project: '项目经历',
  award: '获奖荣誉', availability: '求职意向',
}

async function loadAll() {
  try { jobs.value = await listJobs() } catch {}
  try { evidence.value = (await listEvidence()).filter(e => e.verified) } catch {}
  try { versions.value = await listResumeVersions() } catch {}
}
onMounted(loadAll)

async function handleTailor() {
  if (!selectedJobId.value) { ElMessage.warning('请选择岗位'); return }
  if (!selectedEvidenceIds.value.length) { ElMessage.warning('请选择至少一项履历证据'); return }
  const job = jobs.value.find(j => j.job_id === selectedJobId.value)
  if (!job) return

  loading.value = true
  try {
    const selectedEvi = evidence.value.filter(e => selectedEvidenceIds.value.includes(e.evidence_id))
    const eviTexts = selectedEvi.map(e => `[${e.category}] ${e.content}`)
    const result = await tailorResume(job.raw_description, eviTexts, currentText.value, requestGoal.value)
    tailorResult.value = result
    saveName.value = `${job.company}-${job.title}-定制版`
    ElMessage.success('定制建议已生成')
  } finally { loading.value = false }
}

async function handleSaveVersion() {
  if (!tailorResult.value || !selectedJobId.value) return
  loading.value = true
  try {
    await addResumeVersion({
      job_id: selectedJobId.value,
      name: saveName.value || '定制版本',
      content: tailorResult.value.recommended_text,
      target_category: saveCategory.value,
      fit_assessment: tailorResult.value.fit_assessment,
      evidence_basis: tailorResult.value.evidence_basis,
      gap_notes: tailorResult.value.gap_notes,
    })
    ElMessage.success('版本已保存')
    versions.value = await listResumeVersions()
  } finally { loading.value = false }
}

async function handleExport(format: 'docx' | 'pdf', version?: ResumeVersion) {
  try {
    const blob = await exportResume(format, version ? {
      name: version.name,
      content: version.content,
      target_category: version.target_category,
    } : {})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${version?.name || 'resume'}.${format}`
    a.click()
    URL.revokeObjectURL(url)
  } catch {}
}

async function handleDeleteVersion(id: string) {
  await deleteResumeVersion(id)
  versions.value = await listResumeVersions()
}
</script>

<template>
  <div class="page-header">
    <h2>简历定制</h2>
    <p>基于岗位要求和已确认履历生成定制表述</p>
  </div>

  <!-- 定制表单 -->
  <div class="card-section">
    <h3>生成定制建议</h3>
    <el-form label-width="90px" @submit.prevent="handleTailor">
      <el-form-item label="目标岗位">
        <el-select v-model="selectedJobId" placeholder="选择岗位" style="width:100%">
          <el-option v-for="j in jobs" :key="j.job_id" :label="`${j.company} · ${j.title}`" :value="j.job_id" />
        </el-select>
      </el-form-item>
      <el-form-item label="履历证据">
        <el-select v-model="selectedEvidenceIds" multiple placeholder="选择已确认的履历" style="width:100%">
          <el-option v-for="e in evidence" :key="e.evidence_id" :label="`[${categoryLabels[e.category]}] ${e.content.slice(0, 50)}...`" :value="e.evidence_id" />
        </el-select>
      </el-form-item>
      <el-form-item label="当前简历"><el-input v-model="currentText" type="textarea" :rows="3" placeholder="可选：粘贴当前简历内容" /></el-form-item>
      <el-form-item label="定制要求"><el-input v-model="requestGoal" placeholder="可选：描述定制目标" /></el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading">生成定制建议</el-button>
      </el-form-item>
    </el-form>
  </div>

  <!-- 定制结果 -->
  <div class="card-section" v-if="tailorResult">
    <h3>定制结果</h3>
    <el-descriptions :column="1" border size="small">
      <el-descriptions-item label="适配判断">{{ tailorResult.fit_assessment }}</el-descriptions-item>
      <el-descriptions-item label="证据依据">{{ tailorResult.evidence_basis }}</el-descriptions-item>
      <el-descriptions-item label="缺口提示">{{ tailorResult.gap_notes }}</el-descriptions-item>
    </el-descriptions>

    <h4 style="margin:16px 0 8px">推荐表述</h4>
    <el-input v-model="tailorResult.recommended_text" type="textarea" :rows="8" readonly />

    <!-- 保存版本 -->
    <div style="margin-top:16px">
      <el-row :gutter="16">
        <el-col :span="10"><el-input v-model="saveName" placeholder="版本名称" /></el-col>
        <el-col :span="6">
          <el-select v-model="saveCategory" style="width:100%">
            <el-option v-for="(label, key) in categoryLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-button type="primary" :loading="loading" @click="handleSaveVersion">保存定制版本</el-button>
        </el-col>
      </el-row>
    </div>
  </div>

  <!-- 已保存版本 -->
  <div class="card-section" v-if="versions.length">
    <h3>已保存版本 ({{ versions.length }})</h3>
    <el-collapse>
      <el-collapse-item v-for="v in versions" :key="v.version_id">
        <template #title>
          <div style="flex:1">
            <strong>{{ v.name }}</strong>
            <el-tag size="small" style="margin-left:8px">{{ categoryLabels[v.target_category] || v.target_category }}</el-tag>
            <el-text type="info" size="small" style="margin-left:8px">{{ v.created_at }}</el-text>
          </div>
        </template>
        <div style="white-space:pre-wrap;font-size:13px">{{ v.content }}</div>
        <div style="margin-top:8px;text-align:right">
          <el-button size="small" @click="handleExport('docx', v)">导出 Word</el-button>
          <el-button size="small" @click="handleExport('pdf', v)">导出 PDF</el-button>
          <el-button type="danger" size="small" text @click="handleDeleteVersion(v.version_id)">删除</el-button>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>
