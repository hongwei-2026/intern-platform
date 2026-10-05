<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { PortalLinksOut } from '@/api/types'
import HeroCarousel from '@/components/HeroCarousel.vue'

const links = ref<PortalLinksOut | null>(null)

onMounted(async () => {
  try {
    const { data } = await api.get<PortalLinksOut>('/integrations/links')
    links.value = data
  } catch {
    links.value = null
  }
})

const services = [
  {
    key: 'mirror_url' as const,
    title: '华中科技大学开源镜像站',
    desc: '同步开源软件镜像，支持公网访问',
    icon: 'mirror',
  },
  {
    key: 'gitea_url' as const,
    title: 'Gitea 代码托管平台',
    desc: '代码管理、Issue 与 PR，服务结项核验',
    icon: 'git',
  },
  {
    key: 'docs_url' as const,
    title: '俱乐部公开文档',
    desc: '成员信息、贡献指南与公开资料',
    icon: 'docs',
  },
  {
    key: 'join_guide_url' as const,
    title: '加入我们',
    desc: 'PR 贡献 → 信息表 → 加入 GitHub 组织',
    icon: 'join',
  },
]

const processSteps = [
  { n: '01', title: '社区报名与审核', desc: '社区提交资料，组委会准入', kind: 'org' },
  { n: '02', title: '发布实习项目', desc: '导师发布课题并上线', kind: 'org' },
  { n: '03', title: '学生项目申请', desc: '浏览项目并提交申请书', kind: 'stu' },
  { n: '04', title: '三级审核', desc: '导师 → 社区 → 组委会', kind: 'stu' },
  { n: '05', title: '中选公示', desc: '结果公开，进入开发', kind: 'stu' },
  { n: '06', title: '结项审核与公示', desc: 'PR/报告双审后公示', kind: 'stu' },
]

const track = ref<HTMLElement | null>(null)

function scrollTrack(dir: 1 | -1) {
  const el = track.value
  if (!el) return
  el.scrollBy({ left: dir * 280, behavior: 'smooth' })
}
</script>

<template>
  <div>
    <HeroCarousel />

    <section class="section">
      <div class="value-grid">
        <div class="value-item">
          <div class="value-glyph">项</div>
          <h3>零距离参与开源课题</h3>
          <p>对接俱乐部多 SIG / 社区项目，在真实仓库完成贡献</p>
        </div>
        <div class="value-item">
          <div class="value-glyph">导</div>
          <h3>导师一对一指导</h3>
          <p>申请、审核、结项全流程留痕，沟通可追溯</p>
        </div>
        <div class="value-item">
          <div class="value-glyph">审</div>
          <h3>三级审核与公示</h3>
          <p>导师、社区、组委会节点清晰，中选与结项公开透明</p>
        </div>
      </div>
    </section>

    <section class="section soft">
      <div class="section-head">
        <h2>活动流程</h2>
        <div class="accent-line" />
        <p>可左右滑动查看完整流程</p>
      </div>
      <div class="h-scroll-wrap">
        <button class="h-scroll-btn" type="button" aria-label="向左" @click="scrollTrack(-1)">‹</button>
        <div ref="track" class="process-track h-scroll">
          <div
            v-for="s in processSteps"
            :key="s.n"
            class="process-step"
            :class="s.kind"
          >
            <div class="num">{{ s.n }}</div>
            <h3>{{ s.title }}</h3>
            <p>{{ s.desc }}</p>
          </div>
        </div>
        <button class="h-scroll-btn" type="button" aria-label="向右" @click="scrollTrack(1)">›</button>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>核心服务</h2>
        <div class="accent-line" />
        <p>与华科开放原子俱乐部现有基础设施对接</p>
      </div>
      <div class="service-grid">
        <a
          v-for="s in services"
          :key="s.key"
          class="service-card"
          :href="(links && links[s.key]) || 'https://hust.openatom.club/'"
          target="_blank"
          rel="noopener"
        >
          <div class="service-icon" aria-hidden="true">
            <svg v-if="s.icon === 'mirror'" viewBox="0 0 48 48" fill="none">
              <rect x="10" y="8" width="28" height="8" rx="2" stroke="#374151" stroke-width="2" />
              <rect x="10" y="20" width="28" height="8" rx="2" stroke="#374151" stroke-width="2" />
              <rect x="10" y="32" width="28" height="8" rx="2" stroke="#374151" stroke-width="2" />
            </svg>
            <svg v-else-if="s.icon === 'git'" viewBox="0 0 48 48" fill="none">
              <circle cx="14" cy="24" r="4" stroke="#374151" stroke-width="2" />
              <circle cx="34" cy="12" r="4" stroke="#374151" stroke-width="2" />
              <circle cx="34" cy="36" r="4" stroke="#374151" stroke-width="2" />
              <path d="M18 24h8M26 24l8-10M26 24l8 10" stroke="#374151" stroke-width="2" />
            </svg>
            <svg v-else-if="s.icon === 'docs'" viewBox="0 0 48 48" fill="none">
              <path d="M14 10h14l8 8v20a2 2 0 0 1-2 2H14a2 2 0 0 1-2-2V12a2 2 0 0 1 2-2z" stroke="#374151" stroke-width="2" />
              <path d="M28 10v8h8M18 24h12M18 30h12" stroke="#374151" stroke-width="2" />
            </svg>
            <svg v-else viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="18" r="7" stroke="#374151" stroke-width="2" />
              <path d="M12 38c2.5-7 9-10 12-10s9.5 3 12 10" stroke="#374151" stroke-width="2" />
              <circle cx="34" cy="14" r="5" stroke="#374151" stroke-width="2" />
            </svg>
          </div>
          <strong>{{ s.title }}</strong>
          <span>{{ s.desc }}</span>
        </a>
      </div>
    </section>

    <section class="section soft">
      <div class="section-head">
        <h2>开始参与</h2>
        <div class="accent-line" />
        <p>先阅读参与指南，再浏览项目；登录请点右上角「登录」并选择账户类型</p>
      </div>
      <div class="btn-row" style="justify-content: center">
        <RouterLink class="btn student" to="/projects">浏览项目</RouterLink>
        <RouterLink class="btn secondary" to="/guide">阅读参与指南</RouterLink>
        <RouterLink class="btn secondary" to="/projects?tab=orgs">按社区选择</RouterLink>
      </div>
    </section>
  </div>
</template>
