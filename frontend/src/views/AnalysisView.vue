<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listJobs } from '@/api/jobs'
import { listEvidence } from '@/api/evidence'
import { listAnalyses, analyzeMatch, enhanceAnalysis, addMatchFeedback, listMatchFeedback } from '@/api/analyses'
import { semanticMatch } from '@/api/library'
import type { JobPosting, MatchAnalysis, MatchFeedback, ProfileEvidence } from '@/api/types'

const jobs = ref<JobPosting[]>([])
const evidence = ref<ProfileEvidence[]>([])
const analyses = ref<MatchAnalysis[]>([])
const selectedJobId = ref('')
const loading = ref(false)
const selectedJob = ref<JobPosting | null>(null)
const feedback = ref<MatchFeedback[]>([])
const feedbackForm = reactive({
  rating: 'partially_accurate',
  issue_type: 'missed_skill',
  comment: '',
  correction: '',
})

async function loadJobs() {
  try { jobs.value = await listJobs() } catch {}
}
async function loadEvidence() {
  try { evidence.value = await listEvidence() } catch {}
}

onMounted(() => { loadJobs(); loadEvidence() })

async function onJobChange(jobId: string) {
  selectedJob.value = jobs.value.find(j => j.job_id === jobId) || null
  try { analyses.value = await listAnalyses(jobId) } catch {}
  await loadFeedback()
}

async function runKeywordAnalysis() {
  if (!selectedJobId.value) { ElMessage.warning('请先选择岗位'); return }
  loading.value = true
  try {
    const r = await analyzeMatch(selectedJobId.value)
    analyses.value.unshift(r)
    await loadFeedback()
    ElMessage.success('关键词分析完成')
  } finally { loading.value = false }
}

async function runHybridAnalysis() {
  if (!selectedJobId.value) { ElMessage.warning('请先选择岗位'); return }
  loading.value = true
  try {
    const analysis = await analyzeMatch(selectedJobId.value)
    const verified = evidence.value.filter(e => e.verified)
    const evidenceTuples: [string, string][] = verified.map(e => [e.category, e.content])
    const keywordSummary = `已覆盖: ${analysis.matched_requirements.join(', ')}; 缺少: ${analysis.missing_requirements.join(', ')}`

    const sem = await semanticMatch(selectedJob.value!.raw_description, evidenceTuples, keywordSummary)
    const enhanced = await enhanceAnalysis(analysis.analysis_id, {
      semantic_score: sem.semantic_score,
      semantic_evidence_ids: sem.semantic_evidence_ids,
      model_explanation: sem.model_explanation,
    })
    analyses.value.unshift(enhanced)
    await loadFeedback()
    ElMessage.success('混合分析完成')
  } finally { loading.value = false }
}

async function loadFeedback() {
  const latest = analyses.value[0]
  if (!latest) { feedback.value = []; return }
  try { feedback.value = await listMatchFeedback(latest.analysis_id) } catch {}
}

async function submitFeedback(analysisId: string) {
  if (!feedbackForm.comment.trim() && !feedbackForm.correction.trim()) {
    ElMessage.warning('请填写反馈或修正建议')
    return
  }
  await addMatchFeedback({
    analysis_id: analysisId,
    rating: feedbackForm.rating,
    issue_type: feedbackForm.issue_type,
    comment: feedbackForm.comment,
    correction: feedbackForm.correction,
  })
  feedbackForm.comment = ''
  feedbackForm.correction = ''
  await loadFeedback()
  ElMessage.success('反馈已记录')
}
</script>

<template>
  <div class="page-header">
    <h2>匹配分析</h2>
    <p>分析个人能力与岗位要求的匹配程度</p>
  </div>

  <div class="card-section">
    <el-row :gutter="16" align="middle">
      <el-col :span="10">
        <el-select v-model="selectedJobId" placeholder="选择岗位" @change="onJobChange" style="width:100%">
          <el-option v-for="j in jobs" :key="j.job_id" :label="`${j.company} · ${j.title}`" :value="j.job_id" />
        </el-select>
      </el-col>
      <el-col :span="14">
        <el-button type="primary" :loading="loading" @click="runKeywordAnalysis">运行关键词基线</el-button>
        <el-button type="success" :loading="loading" @click="runHybridAnalysis">运行混合分析</el-button>
      </el-col>
    </el-row>
  </div>

  <!-- 分析结果 -->
  <template v-if="analyses.length">
    <div class="card-section" v-for="a in analyses.slice(0, 1)" :key="a.analysis_id">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:12px">
        <el-statistic title="综合分数" :value="a.score" :precision="1" suffix="/100" />
        <el-statistic v-if="a.keyword_score != null" title="关键词" :value="a.keyword_score" :precision="1" />
        <el-statistic v-if="a.semantic_score != null" title="语义" :value="a.semantic_score" :precision="1" />
        <el-tag v-if="a.is_stale" type="warning">需重算</el-tag>
        <el-tag :type="a.analysis_type === 'hybrid' ? 'success' : 'info'">{{ a.analysis_type === 'hybrid' ? '混合分析' : '关键词基线' }}</el-tag>
      </div>

      <el-row :gutter="16">
        <el-col :span="12">
          <h4 style="margin:0 0 8px;color:#67C23A">已覆盖技能</h4>
          <el-tag v-for="s in a.matched_requirements" :key="s" size="small" type="success" style="margin:2px">{{ s }}</el-tag>
          <el-tag v-for="s in a.matched_preferred_skills" :key="s" size="small" style="margin:2px">{{ s }}</el-tag>
        </el-col>
        <el-col :span="12">
          <h4 style="margin:0 0 8px;color:#F56C6C">缺少技能</h4>
          <el-tag v-for="s in a.missing_requirements" :key="s" size="small" type="danger" style="margin:2px">{{ s }}</el-tag>
          <el-tag v-for="s in a.missing_preferred_skills" :key="s" size="small" type="warning" style="margin:2px">{{ s }}</el-tag>
        </el-col>
      </el-row>

      <div v-if="a.resume_suggestions?.length" style="margin-top:12px">
        <h4 style="margin:0 0 8px">建议</h4>
        <el-alert v-for="(s, i) in a.resume_suggestions" :key="i" :title="s" type="info" show-icon :closable="false" style="margin-bottom:4px" />
      </div>

      <div v-if="a.suggestion_cards?.length" style="margin-top:12px">
        <h4 style="margin:0 0 8px">证据绑定建议</h4>
        <el-table :data="a.suggestion_cards" size="small" border>
          <el-table-column prop="skill" label="技能" width="120" />
          <el-table-column prop="suggestion" label="建议" />
          <el-table-column label="证据" min-width="220">
            <template #default="{ row }">
              <div style="font-size:12px;color:var(--color-muted);white-space:pre-wrap">
                {{ row.evidence_ids?.join(', ') || '-' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="风险" width="90">
            <template #default="{ row }">
              <el-tag :type="row.risk_level === 'low' ? 'success' : 'warning'" size="small">{{ row.risk_level }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="a.risk_flags?.length" style="margin-top:12px">
        <h4 style="margin:0 0 8px">防幻觉风险</h4>
        <el-alert v-for="(flag, i) in a.risk_flags" :key="i" :title="flag" type="warning" show-icon :closable="false" style="margin-bottom:4px" />
      </div>

      <div v-if="a.model_explanation" style="margin-top:12px">
        <h4 style="margin:0 0 8px">模型解释</h4>
        <p style="font-size:13px;color:var(--color-muted);margin:0;white-space:pre-wrap">{{ a.model_explanation }}</p>
      </div>

      <div style="margin-top:16px">
        <h4 style="margin:0 0 8px">分析反馈</h4>
        <el-form label-width="80px">
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item label="准确性">
                <el-select v-model="feedbackForm.rating" style="width:100%">
                  <el-option label="基本准确" value="accurate" />
                  <el-option label="部分准确" value="partially_accurate" />
                  <el-option label="明显错误" value="wrong" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="问题">
                <el-select v-model="feedbackForm.issue_type" style="width:100%">
                  <el-option label="漏匹配技能" value="missed_skill" />
                  <el-option label="证据不相关" value="irrelevant_evidence" />
                  <el-option label="幻觉表述" value="hallucination" />
                  <el-option label="分数不准" value="wrong_score" />
                  <el-option label="引用错误" value="wrong_citation" />
                  <el-option label="其他" value="other" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-button type="primary" style="width:100%" @click="submitFeedback(a.analysis_id)">记录反馈</el-button>
            </el-col>
          </el-row>
          <el-form-item label="反馈">
            <el-input v-model="feedbackForm.comment" placeholder="例如：FastAPI 被漏匹配，证据在项目经历中。" />
          </el-form-item>
          <el-form-item label="修正">
            <el-input v-model="feedbackForm.correction" placeholder="可选：写下正确判断，后续可沉淀为评测样本。" />
          </el-form-item>
        </el-form>
        <el-table v-if="feedback.length" :data="feedback" size="small">
          <el-table-column prop="rating" label="准确性" width="120" />
          <el-table-column prop="issue_type" label="问题" width="140" />
          <el-table-column prop="comment" label="反馈" />
          <el-table-column prop="created_at" label="时间" width="160" />
        </el-table>
      </div>
    </div>

    <!-- 历史分析 -->
    <div class="card-section" v-if="analyses.length > 1">
      <h3>分析历史</h3>
      <el-table :data="analyses" size="small">
        <el-table-column prop="analysis_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.analysis_type === 'hybrid' ? 'success' : 'info'" size="small">{{ row.analysis_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="分数" width="80">
          <template #default="{ row }">{{ row.score?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="keyword_score" label="关键词" width="80">
          <template #default="{ row }">{{ row.keyword_score?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="semantic_score" label="语义" width="80">
          <template #default="{ row }">{{ row.semantic_score?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" />
      </el-table>
    </div>
  </template>
</template>
