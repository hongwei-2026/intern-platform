<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import api from '@/api/client'
import type { CommunityOut, ProjectOut } from '@/api/types'
import CommunityIntroView from '@/components/CommunityIntroView.vue'
import PageCrumb from '@/components/PageCrumb.vue'
import { difficultyLabel, stackLabel } from '@/utils/projectBrief'
import { resolveCrumbs, seedTrail } from '@/utils/crumbTrail'

const route = useRoute()

const community = ref<CommunityOut | null>(null)
const projects = ref<ProjectOut[]>([])
const error = ref('')
const loading = ref(true)

function parseStack(raw?: string | null): string[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    if (Array.isArray(v)) return v.map(String).filter(Boolean)
  } catch {
    /* plain */
  }
  return raw
    .split(/[,，|/]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

const langTags = computed(() => {
  if (community.value?.tags?.length) return community.value.tags
  const tags = new Set<string>()
  for (const p of projects.value) {
    for (const t of parseStack(p.tech_stack)) tags.add(t)
  }
  return [...tags].slice(0, 12)
})

const domainGuess = computed(() => {
  if (community.value?.tags?.length) return []
  const raw = [
    community.value?.name,
    community.value?.description,
    ...projects.value.map((p) => p.summary || p.title),
  ]
    .filter(Boolean)
    .join(' ')
  const keys = ['内核', '驱动', '镜像', '文档', '工具', 'AI', '深度学习', '运维', '前端', '后端']
  return keys.filter((k) => raw.includes(k)).slice(0, 6)
})

const crumbs = computed(() => {
  const c = community.value
  if (!c) return [{ label: '社区主页' }]
  return resolveCrumbs(
    { label: c.name, to: `/communities/${c.slug}` },
    [{ label: '查看项目', to: '/projects' }],
  )
})

/** 进入任务介绍前固化「查看项目 › 本社区」父路径 */
function beforeOpenProject() {
  const c = community.value
  if (!c) return
  seedTrail([
    { label: '查看项目', to: '/projects' },
    { label: c.name, to: `/communities/${c.slug}` },
  ])
}

function initialOf(name: string) {
  return (name || '?').trim().slice(0, 1).toUpperCase()
}

async function load() {
  loading.value = true
  error.value = ''
  community.value = null
  projects.value = []
  const slug = String(route.params.slug)
  try {
    const { data } = await api.get<CommunityOut>(`/communities/${slug}`)
    community.value = data
    const { data: projs } = await api.get<ProjectOut[]>('/projects', {
      params: { community_id: data.id, status: 'published' },
    })
    projects.value = projs
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params.slug, load)
</script>

<template>
  <div class="ospp-org">
    <PageCrumb :items="crumbs" />

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else-if="community">
      <!-- 开源之夏风格：Logo + 名称 + 外链 + 简介 + 结构化信息 -->
      <header class="org-profile">
        <div class="org-logo" aria-hidden="true">
          <img v-if="community.logo_url" :src="community.logo_url" :alt="community.name" />
          <span v-else>{{ initialOf(community.name) }}</span>
        </div>
        <div class="org-body">
          <h1>{{ community.name }}</h1>
          <a
            v-if="community.homepage_url"
            class="official-link"
            :href="community.homepage_url"
            target="_blank"
            rel="noopener"
          >
            官网主页：点击前往 ›
          </a>
          <p v-else class="official-miss">暂未填写官网主页</p>

          <p class="org-desc">
            {{
              community.description ||
              '该社区暂未填写一句话简介。社区管理员可在组织工作台完善对外介绍。'
            }}
          </p>

          <ul class="org-meta">
            <li v-if="community.gitea_org_url || community.homepage_url">
              <span class="ico ico-repo" aria-hidden="true"></span>
              <div>
                <em>主要仓库 / 组织地址</em>
                <a
                  :href="community.gitea_org_url || community.homepage_url || '#'"
                  target="_blank"
                  rel="noopener"
                >{{ community.gitea_org_url || community.homepage_url }}</a>
              </div>
            </li>
            <li v-if="community.mirror_doc_url">
              <span class="ico ico-doc" aria-hidden="true"></span>
              <div>
                <em>文档 / 镜像</em>
                <a :href="community.mirror_doc_url" target="_blank" rel="noopener">{{
                  community.mirror_doc_url
                }}</a>
              </div>
            </li>
            <li v-if="community.tags?.length || domainGuess.length || langTags.length">
              <span class="ico ico-field" aria-hidden="true"></span>
              <div>
                <em>社区标签</em>
                <div class="tags">
                  <span
                    v-for="t in community.tags?.length ? community.tags : [...domainGuess, ...langTags].slice(0, 12)"
                    :key="t"
                    class="tag"
                  >{{ t }}</span>
                </div>
              </div>
            </li>
            <li>
              <span class="ico ico-task" aria-hidden="true"></span>
              <div>
                <em>可接取任务</em>
                <strong class="num">{{ projects.length }}</strong>
              </div>
            </li>
          </ul>
        </div>
      </header>

      <section class="intro-sec">
        <h2>社区介绍</h2>
        <CommunityIntroView :body="community.intro_body" :fallback="null" />
      </section>

      <section class="task-sec">
        <div class="sec-head">
          <h2>社区任务</h2>
          <span class="muted">共 {{ projects.length }} 项</span>
        </div>
        <div v-if="!projects.length" class="empty">该社区暂无已发布任务。</div>
        <div v-else class="task-list">
          <article v-for="p in projects" :key="p.id" class="task-row">
            <div class="task-main">
              <h3>
                <RouterLink :to="`/projects/${p.id}`" @click="beforeOpenProject">{{
                  p.title
                }}</RouterLink>
              </h3>
              <p>{{ p.summary || '暂无摘要' }}</p>
              <div class="tags">
                <span v-for="t in parseStack(p.tech_stack).slice(0, 4)" :key="t" class="tag">{{
                  stackLabel(t)
                }}</span>
                <span v-if="p.difficulty" class="tag soft">{{ difficultyLabel(p.difficulty) }}</span>
                <span class="tag soft">名额 {{ p.quota }}</span>
              </div>
            </div>
            <RouterLink class="btn-go" :to="`/projects/${p.id}`" @click="beforeOpenProject"
              >查看任务</RouterLink
            >
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.ospp-org {
  max-width: 920px;
  margin: 0 auto;
  padding: 28px 20px 72px;
  background: #fff;
  min-height: calc(100vh - var(--nav-h, 64px));
}
.org-profile {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 28px;
  padding: 8px 0 36px;
  border-bottom: 1px solid #f0f0f0;
}
.org-logo {
  width: 96px;
  height: 96px;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
  background: #fafafa;
  display: grid;
  place-items: center;
  overflow: hidden;
  font-size: 36px;
  font-weight: 700;
  color: #1677ff;
}
.org-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.org-body h1 {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 700;
  color: #262626;
  letter-spacing: -0.02em;
}
.official-link {
  display: inline-block;
  margin-bottom: 16px;
  color: #1677ff;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}
.official-link:hover {
  text-decoration: underline;
}
.official-miss {
  margin: 0 0 16px;
  color: #bfbfbf;
  font-size: 13px;
}
.org-desc {
  margin: 0 0 22px;
  color: #595959;
  font-size: 15px;
  line-height: 1.75;
  max-width: 640px;
}
.org-meta {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.org-meta li {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
  align-items: start;
}
.ico {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e6f4ff;
  position: relative;
  flex-shrink: 0;
}
.ico::before {
  content: '';
  position: absolute;
  inset: 0;
  margin: auto;
  background: #1677ff;
}
.ico-repo::before {
  width: 12px;
  height: 10px;
  border-radius: 2px;
  box-shadow: 2px 2px 0 #91caff;
  background: #1677ff;
}
.ico-doc::before {
  width: 9px;
  height: 12px;
  border-radius: 1px;
  background: #1677ff;
}
.ico-field::before {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 6px 0 0 #91caff, 3px 5px 0 #69b1ff;
  background: #1677ff;
  left: -3px;
}
.ico-lang::before {
  width: 10px;
  height: 2px;
  box-shadow: 0 4px 0 #1677ff, 0 8px 0 #1677ff;
  background: #1677ff;
  top: 8px;
}
.ico-task::before {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  border: 2px solid #1677ff;
  background: transparent;
  box-sizing: border-box;
}
.org-meta em {
  display: block;
  font-style: normal;
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 2px;
}
.org-meta a {
  color: #262626;
  word-break: break-all;
  text-decoration: none;
  font-size: 14px;
}
.org-meta a:hover {
  color: #1677ff;
}
.num {
  font-size: 15px;
  color: #262626;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag {
  display: inline-flex;
  padding: 2px 10px;
  border-radius: 4px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 12px;
  font-weight: 600;
}
.tag.soft {
  background: #f5f5f5;
  color: #595959;
}
.task-sec {
  padding-top: 36px;
}
.intro-sec {
  padding-top: 36px;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 28px;
}
.intro-sec h2 {
  margin: 0 0 16px;
  font-size: 18px;
  color: #262626;
}
.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
}
.sec-head h2 {
  margin: 0;
  font-size: 18px;
  color: #262626;
}
.task-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-top: 1px solid #f0f0f0;
}
.task-row {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding: 20px 4px;
  border-bottom: 1px solid #f0f0f0;
}
.task-main h3 {
  margin: 0 0 6px;
  font-size: 16px;
}
.task-main h3 a {
  color: #262626;
  text-decoration: none;
}
.task-main h3 a:hover {
  color: #1677ff;
}
.task-main p {
  margin: 0 0 10px;
  color: #8c8c8c;
  font-size: 13px;
  line-height: 1.5;
}
.btn-go {
  flex-shrink: 0;
  padding: 8px 18px;
  border-radius: 4px;
  background: #1677ff;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}
.btn-go:hover {
  background: #4096ff;
}
.empty {
  padding: 28px;
  text-align: center;
  color: #8c8c8c;
  background: #fafafa;
  border-radius: 8px;
}
@media (max-width: 640px) {
  .org-profile {
    grid-template-columns: 1fr;
  }
  .task-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
