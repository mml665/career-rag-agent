<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listJobs } from '@/api/jobs'
import { listResumeVersions } from '@/api/resume'
import { listApplications, addApplication, updateApplication, deleteApplication } from '@/api/applications'
import { listAnalyses } from '@/api/analyses'
import type { JobPosting, ResumeVersion, ApplicationRecord, MatchAnalysis } from '@/api/types'

const jobs = ref<JobPosting[]>([])
const versions = ref<ResumeVersion[]>([])
const applications = ref<ApplicationRecord[]>([])
const analyses = ref<MatchAnalysis[]>([])
const loading = ref(false)

const statusLabels: Record<string, string> = {
  planned: '准备投递', submitted: '已投递', written_test: '笔试',
  interview: '面试', offer: 'Offer', closed: '结束',
}
const statusTypes: Record<string, string> = {
  planned: 'info', submitted: '', written_test: 'warning',
  interview: 'warning', offer: 'success', closed: 'info',
}

const newForm = ref({ job_id: '', status: 'planned', resume_version: '', resume_version_id: '', submitted_at: '', notes: '' })

async function loadAll() {
  try { jobs.value = await listJobs() } catch {}
  try { versions.value = await listResumeVersions() } catch {}
  try { applications.value = await listApplications() } catch {}
  try { analyses.value = await listAnalyses() } catch {}
}
onMounted(loadAll)

function getJobName(jobId: string) {
  const j = jobs.value.find(j => j.job_id === jobId)
  return j ? `${j.company} · ${j.title}` : jobId
}

async function handleAdd() {
  if (!newForm.value.job_id) { ElMessage.warning('请选择岗位'); return }
  loading.value = true
  try {
    const latestAnalysis = analyses.value.find(a => a.job_id === newForm.value.job_id)
    await addApplication({
      ...newForm.value,
      analysis_id: latestAnalysis?.analysis_id || '',
    })
    ElMessage.success('投递记录已创建')
    newForm.value = { job_id: '', status: 'planned', resume_version: '', resume_version_id: '', submitted_at: '', notes: '' }
    await loadAll()
  } finally { loading.value = false }
}

async function handleUpdate(id: string, data: Partial<ApplicationRecord>) {
  await updateApplication(id, data)
  await loadAll()
}

async function handleDelete(id: string) {
  await deleteApplication(id)
  await loadAll()
}
</script>

<template>
  <div class="page-header">
    <h2>投递记录</h2>
    <p>跟踪投递状态，关联简历版本</p>
  </div>

  <!-- 新建记录 -->
  <div class="card-section">
    <h3>新建投递记录</h3>
    <el-form label-width="90px" @submit.prevent="handleAdd">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="岗位">
            <el-select v-model="newForm.job_id" placeholder="选择岗位" style="width:100%">
              <el-option v-for="j in jobs" :key="j.job_id" :label="`${j.company} · ${j.title}`" :value="j.job_id" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="4">
          <el-form-item label="状态">
            <el-select v-model="newForm.status" style="width:100%">
              <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="简历版本">
            <el-select v-model="newForm.resume_version_id" placeholder="选择版本" style="width:100%" clearable
              @change="(val: string) => { const v = versions.find(v => v.version_id === val); newForm.resume_version = v?.name || '' }">
              <el-option v-for="v in versions" :key="v.version_id" :label="v.name" :value="v.version_id" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="投递时间">
            <el-date-picker v-model="newForm.submitted_at" type="date" value-format="YYYY-MM-DD" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="备注"><el-input v-model="newForm.notes" /></el-form-item>
      <el-form-item><el-button type="primary" native-type="submit" :loading="loading">创建记录</el-button></el-form-item>
    </el-form>
  </div>

  <!-- 已有记录 -->
  <div class="card-section" v-if="applications.length">
    <h3>投递记录 ({{ applications.length }})</h3>
    <el-table :data="applications" size="small">
      <el-table-column label="岗位" min-width="200">
        <template #default="{ row }">{{ getJobName(row.job_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="(statusTypes[row.status] as any) || ''" size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="resume_version" label="简历版本" width="160">
        <template #default="{ row }">{{ row.resume_version || '-' }}</template>
      </el-table-column>
      <el-table-column prop="submitted_at" label="投递时间" width="120" />
      <el-table-column prop="notes" label="备注" show-overflow-tooltip />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button type="danger" size="small" text @click="handleDelete(row.application_id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
