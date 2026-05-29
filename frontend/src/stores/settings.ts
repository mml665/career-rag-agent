import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const chunkSize = ref(700)
  const chunkOverlap = ref(120)
  const topK = ref(4)
  const minRelevanceScore = ref(0.45)
  const enableBm25 = ref(true)
  const bm25Weight = ref(0.3)
  const rrfK = ref(60)
  const enableRerank = ref(true)
  const rerankTopN = ref(10)

  const vectorWeight = computed(() => +(1 - bm25Weight.value).toFixed(2))

  return {
    chunkSize, chunkOverlap, topK, minRelevanceScore,
    enableBm25, bm25Weight, vectorWeight, rrfK,
    enableRerank, rerankTopN,
  }
})
