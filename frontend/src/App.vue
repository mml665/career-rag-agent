<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/profile', title: '个人档案', icon: 'User' },
  { path: '/jobs', title: '岗位库', icon: 'Briefcase' },
  { path: '/analysis', title: '匹配分析', icon: 'DataAnalysis' },
  { path: '/resume', title: '简历定制', icon: 'Document' },
  { path: '/applications', title: '投递记录', icon: 'Promotion' },
  { path: '/library', title: '参考资料库', icon: 'Collection' },
  { path: '/agent', title: '智能助手', icon: 'ChatDotRound' },
]
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-logo">智能求职 Agent</div>
    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: route.path === item.path }"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        {{ item.title }}
      </router-link>
    </nav>
    <div class="sidebar-footer">
      <el-text type="info" size="small">v1.0.0</el-text>
    </div>
  </div>
  <main class="main-content">
    <router-view />
  </main>
</template>
