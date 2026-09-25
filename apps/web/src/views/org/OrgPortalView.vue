<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import api from '@/api/client'
import ToastFeedback from '@/components/ToastFeedback.vue'
import LogoUploadField from '@/components/LogoUploadField.vue'
import CommunityIntroEditor from '@/components/CommunityIntroEditor.vue'
import CommunityIntroView from '@/components/CommunityIntroView.vue'
import type { CommunityIntroBody, CommunityMemberOut, CommunityOut, ProjectOut } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { projectStatusLabel, statusTone } from '@/utils/statusLabel'

type Tab = 'home' | 'mentors' | 'projects'

const auth = useAuthStore()
const router = useRouter()
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

const tab = ref<Tab>('home')
const myCommunity = ref<CommunityOut | null>(null)
const mentors = ref<CommunityMemberOut[]>([])
const orgProjects = ref<ProjectOut[]>([])
const busy = ref(false)
const showInvite = ref(false)

const projectForm = ref({
  mentor_id: '' as string | number,
  title: '',
  summary: '',
  description: '',
  tech_stack: '',
  difficulty: 'medium',
  quota: 1,
  repo_url: '',
})

const homeForm = ref({
  name: '',
  description: '',
  homepage_url: '',
  gitea_org_url: '',
  mirror_doc_url: '',
  logo_url: '',
  tags: [] as string[],
  intro_body: { blocks: [] } as CommunityIntroBody,
})

const isCommittee = computed(() => auth.hasRole('committee'))
const isCommunityAdmin = computed(() => auth.hasRole('community_admin'))

/** 右侧预览：去掉空段落，强制随 intro 变化刷新 */
const previewIntro = computed(() => {
  const blocks = homeForm.value.intro_body?.blocks || []
  return {
    blocks: blocks.filter((b) => {
      if (b.type === 'paragraph' || b.type === 'heading') return !!(b.text && b.text.trim())
      if (b.type === 'image' || b.type === 'video') return !!(b.url && String(b.url).trim())
      return true
    }),
  }
})
const previewIntroKey = computed(() =>
  (homeForm.value.intro_body?.blocks || [])
    .map((b) => `${b.type}:${b.url || ''}:${(b.text || '').slice(0, 24)}`)
    .join('|'),
)

function mentorName(project: ProjectOut) {
  const hit = mentors.value.find((m) => m.user_id === project.mentor_id)
  return hit ? hit.display_name || hit.email : `导师 #${project.mentor_id}`
}

function syncHomeForm(c: CommunityOut) {
  homeForm.value = {
    name: c.name || '',
    description: c.description || '',
    homepage_url: c.homepage_url || '',
    gitea_org_url: c.gitea_org_url || '',
    mirror_doc_url: c.mirror_doc_url || '',
    logo_url: c.logo_url || '',
    tags: [...(c.tags || [])],
    intro_body: c.intro_body?.blocks?.length
      ? { blocks: c.intro_body.blocks.map((b) => ({ ...b })) }
      : { blocks: [] },
  }
}

async function loadMentors() {
  if (!myCommunity.value) {
    mentors.value = []
    return
  }
  try {
    const { data } = await api.get<CommunityMemberOut[]>(
      `/communities/${myCommunity.value.id}/members`,
      { params: { role: 'mentor' } },
    )
    mentors.value = data
  } catch {
    mentors.value = []
  }
}

async function loadProjects() {
  if (!myCommunity.value) {
    orgProjects.value = []
    return
  }
  const cid = myCommunity.value.id
  const [d, p] = await Promise.all([
    api.get<ProjectOut[]>('/projects', { params: { community_id: cid, status: 'draft' } }),
    api.get<ProjectOut[]>('/projects', { params: { community_id: cid, status: 'published' } }),
  ])
  const map = new Map<number, ProjectOut>()
  for (const row of [...d.data, ...p.data]) map.set(row.id, row)
  orgProjects.value = [...map.values()].sort((a, b) => b.id - a.id)
}

async function load() {
  try {
    const { data } = await api.get<CommunityOut[]>('/communities/admin-of')
    myCommunity.value = data[0] || null
    if (myCommunity.value) {
      syncHomeForm(myCommunity.value)
      await Promise.all([loadMentors(), loadProjects()])
    }
  } catch {
    myCommunity.value = null
  }
}

async function saveHome() {
  if (!myCommunity.value) return
  busy.value = true
  try {
    const { data } = await api.patch<CommunityOut>(`/communities/${myCommunity.value.id}`, {
      name: homeForm.value.name.trim(),
      description: homeForm.value.description || null,
      homepage_url: homeForm.value.homepage_url || null,
      gitea_org_url: homeForm.value.gitea_org_url || null,
      mirror_doc_url: homeForm.value.mirror_doc_url || null,
      logo_url: homeForm.value.logo_url || null,
      tags: homeForm.value.tags,
      intro_body: homeForm.value.intro_body,
    })
    myCommunity.value = data
    syncHomeForm(data)
    toast.value?.show('已发布到公开主页', 'ok')
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '保存失败', 'err')
  } finally {
    busy.value = false
  }
}

async function saveIntroOnly() {
  await saveHome()
}

async function copyInvite() {
  const code = myCommunity.value?.invite_code
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    toast.value?.show('已复制，请私下发给导师', 'ok')
  } catch {
    toast.value?.show(code, 'ok')
  }
}

async function reassignMentor(projectId: number, mentorId: string) {
  const mid = Number(mentorId)
  if (!mid) return
  busy.value = true
  try {
    await api.patch(`/projects/${projectId}`, { mentor_id: mid })
    toast.value?.show('已改派', 'ok')
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '改派失败', 'err')
  } finally {
    busy.value = false
  }
}

function onReassignChange(projectId: number, event: Event) {
  const el = event.target as HTMLSelectElement
  void reassignMentor(projectId, el.value)
}

async function createProject() {
  if (!myCommunity.value) return
  busy.value = true
  try {
    await api.post<ProjectOut>('/projects', {
      community_id: myCommunity.value.id,
      mentor_id: Number(projectForm.value.mentor_id),
      title: projectForm.value.title.trim(),
      summary: projectForm.value.summary || null,
      description: projectForm.value.description || null,
      tech_stack: projectForm.value.tech_stack
        ? projectForm.value.tech_stack.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
        : null,
      difficulty: projectForm.value.difficulty || null,
      quota: Number(projectForm.value.quota) || 1,
      repo_url: projectForm.value.repo_url || null,
    })
    toast.value?.show('项目已创建', 'ok')
    projectForm.value = {
      ...projectForm.value,
      title: '',
      summary: '',
      description: '',
      mentor_id: '',
    }
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '创建失败', 'err')
  } finally {
    busy.value = false
  }
}

async function publish(id: number) {
  busy.value = true
  try {
    await api.post(`/projects/${id}/publish`)
    toast.value?.show('已发布', 'ok')
    await loadProjects()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '发布失败', 'err')
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  if (isCommittee.value && !isCommunityAdmin.value) {
    router.replace('/committee')
    return
  }
  if (auth.hasRole('mentor') && !isCommunityAdmin.value && !isCommittee.value) {
    router.replace('/mentor')
    return
  }
  await load()
})
</script>

<template>
  <div class="page wide org-console">
    <ToastFeedback ref="toast" />

    <header class="head">
      <div>
        <h1>{{ myCommunity?.name || '组织工作台' }}</h1>
        <p class="sub">管理后台 · 与公开「组织主页」分离</p>
      </div>
      <div class="head-actions" v-if="myCommunity">
        <RouterLink class="link" :to="`/communities/${myCommunity.slug}`" target="_blank"
          >查看公开主页 ›</RouterLink
        >
        <RouterLink class="link muted" to="/community/reviews">审核队列</RouterLink>
      </div>
    </header>

    <section v-if="!myCommunity" class="panel">
      <p class="muted">尚未绑定可管理的社区，请联系组委会开通。</p>
    </section>

    <template v-else>
      <nav class="tabs" aria-label="管理分区">
        <button type="button" :class="{ on: tab === 'home' }" @click="tab = 'home'">社区主页</button>
        <button type="button" :class="{ on: tab === 'mentors' }" @click="tab = 'mentors'">
          导师 <span>{{ mentors.length }}</span>
        </button>
        <button type="button" :class="{ on: tab === 'projects' }" @click="tab = 'projects'">
          项目 <span>{{ orgProjects.length }}</span>
        </button>
      </nav>

      <!-- Tab: 主页 — 左编辑 / 右预览 -->
      <section v-if="tab === 'home'" class="panel home-panel">
        <div class="panel-bar">
          <div>
            <h2>对外展示</h2>
            <p class="bar-hint">左侧编辑，右侧即时预览公开主页效果</p>
          </div>
          <button class="btn" type="button" :disabled="busy" @click="saveHome">
            {{ busy ? '发布中…' : '发布到公开主页' }}
          </button>
        </div>

        <div class="split">
          <!-- 左：创作区 -->
          <div class="pane edit-pane">
            <h3 class="pane-title">编辑</h3>

            <div class="block basic-block">
              <h4>基本信息</h4>
              <div class="basic-grid">
                <LogoUploadField v-model="homeForm.logo_url" class="basic-logo" />
                <label class="span-2">名称<input v-model="homeForm.name" required /></label>
                <label class="span-2"
                  >一句话简介<textarea
                    v-model="homeForm.description"
                    rows="2"
                    placeholder="列表与主页顶部展示"
                  /></label>
                <label>官网<input v-model="homeForm.homepage_url" type="url" placeholder="https://" /></label>
                <label>仓库 / Gitea<input v-model="homeForm.gitea_org_url" type="url" /></label>
                <label class="span-2">文档 / 镜像<input v-model="homeForm.mirror_doc_url" type="url" /></label>
              </div>
            </div>

            <div class="block create-block">
              <h4>创作介绍</h4>
              <CommunityIntroEditor
                v-model="homeForm.intro_body"
                v-model:tags="homeForm.tags"
                compact
                @publish="saveIntroOnly"
              />
            </div>
          </div>

          <!-- 右：预览区 -->
          <aside class="pane preview-pane">
            <h3 class="pane-title">预览 · 公开主页效果</h3>
            <div class="live">
              <header class="live-head">
                <div class="live-logo">
                  <img v-if="homeForm.logo_url" :src="homeForm.logo_url" alt="" />
                  <span v-else>{{ (homeForm.name || '?').slice(0, 1) }}</span>
                </div>
                <div>
                  <h4>{{ homeForm.name || '社区名称' }}</h4>
                  <a
                    v-if="homeForm.homepage_url"
                    class="live-link"
                    :href="homeForm.homepage_url"
                    target="_blank"
                    rel="noopener"
                  >官网主页：点击前往 ›</a>
                  <p v-else class="live-miss">暂未填写官网</p>
                </div>
              </header>
              <p class="live-desc">{{ homeForm.description || '一句话简介会出现在这里' }}</p>
              <div v-if="homeForm.tags.length" class="live-tags">
                <span v-for="t in homeForm.tags" :key="t">{{ t }}</span>
              </div>
              <div v-else class="live-miss">标签会出现在这里</div>
              <div class="live-intro">
                <CommunityIntroView
                  :key="previewIntroKey"
                  :body="previewIntro"
                  fallback="介绍正文、图片、视频会显示在这里"
                />
              </div>
            </div>
          </aside>
        </div>
      </section>

      <!-- Tab: 导师 -->
      <section v-else-if="tab === 'mentors'" class="panel">
        <h2>导师邀请</h2>
        <p class="hint">导师在登录页用邀请码自助注册。邀请码默认隐藏，勿公开给学生。</p>
        <div class="invite">
          <code>{{ showInvite ? myCommunity.invite_code || '—' : '••••••••' }}</code>
          <button class="btn sm secondary" type="button" @click="showInvite = !showInvite">
            {{ showInvite ? '隐藏' : '显示' }}
          </button>
          <button class="btn sm" type="button" @click="copyInvite">复制</button>
        </div>

        <h3 class="subh">已加入（{{ mentors.length }}）</h3>
        <div v-if="!mentors.length" class="empty">暂无导师</div>
        <div v-else class="scroll">
          <table>
            <thead>
              <tr>
                <th>姓名</th>
                <th>邮箱</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in mentors" :key="m.user_id">
                <td>{{ m.display_name }}</td>
                <td>{{ m.email }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Tab: 项目 -->
      <section v-else class="panel">
        <h2>创建并分配导师</h2>
        <form class="form proj" @submit.prevent="createProject">
          <label>
            导师
            <select v-model="projectForm.mentor_id" required>
              <option disabled value="">选择</option>
              <option v-for="m in mentors" :key="m.user_id" :value="m.user_id">
                {{ m.display_name }}
              </option>
            </select>
          </label>
          <label>标题<input v-model="projectForm.title" required /></label>
          <label class="full">摘要<input v-model="projectForm.summary" /></label>
          <label class="full">详情<textarea v-model="projectForm.description" rows="3" /></label>
          <label>技术栈<input v-model="projectForm.tech_stack" /></label>
          <label>
            难度
            <select v-model="projectForm.difficulty">
              <option value="easy">基础</option>
              <option value="medium">进阶</option>
              <option value="hard">挑战</option>
            </select>
          </label>
          <label>名额<input v-model.number="projectForm.quota" type="number" min="1" /></label>
          <label>仓库<input v-model="projectForm.repo_url" type="url" /></label>
          <div class="full">
            <button class="btn" type="submit" :disabled="busy || !mentors.length">创建</button>
          </div>
        </form>

        <h3 class="subh">项目列表（{{ orgProjects.length }}）</h3>
        <div v-if="!orgProjects.length" class="empty">暂无项目</div>
        <div v-else class="scroll tall">
          <table>
            <thead>
              <tr>
                <th>项目</th>
                <th>状态</th>
                <th>导师</th>
                <th>改派</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in orgProjects" :key="p.id">
                <td>
                  <RouterLink :to="`/projects/${p.id}`">{{ p.title }}</RouterLink>
                </td>
                <td>
                  <span class="badge" :class="statusTone(p.status)">{{
                    projectStatusLabel(p.status)
                  }}</span>
                </td>
                <td>{{ mentorName(p) }}</td>
                <td>
                  <select
                    :value="p.mentor_id"
                    :disabled="busy"
                    @change="onReassignChange(p.id, $event)"
                  >
                    <option v-for="m in mentors" :key="m.user_id" :value="m.user_id">
                      {{ m.display_name }}
                    </option>
                  </select>
                </td>
                <td>
                  <button
                    v-if="p.status === 'draft'"
                    class="btn sm"
                    type="button"
                    :disabled="busy"
                    @click="publish(p.id)"
                  >
                    发布
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.org-console {
  max-width: none;
  margin: 0 auto;
  padding: 0.85rem 1.75rem 1.75rem;
  width: 100%;
  box-sizing: border-box;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-end;
  margin-bottom: 1.25rem;
}
.head h1 {
  margin: 0;
  font-size: 1.45rem;
  color: #262626;
}
.sub {
  margin: 0.25rem 0 0;
  color: #8c8c8c;
  font-size: 0.86rem;
}
.head-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}
.link {
  color: #1677ff;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
}
.link.muted {
  color: #8c8c8c;
  font-weight: 500;
}
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 0;
  border-bottom: 1px solid #f0f0f0;
}
.tabs button {
  border: none;
  background: transparent;
  padding: 0.7rem 1.1rem;
  font-size: 0.92rem;
  color: #8c8c8c;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tabs button.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom-color: #1677ff;
}
.tabs span {
  margin-left: 0.25rem;
  font-size: 0.78rem;
  color: #bfbfbf;
}
.panel {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-top: none;
  border-radius: 0 0 10px 10px;
  padding: 1.25rem 1.35rem 1.5rem;
}
.panel-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.panel-bar h2 {
  margin: 0;
}
.bar-hint {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: #8c8c8c;
}
.hint {
  margin: 0 0 0.85rem;
  color: #8c8c8c;
  font-size: 0.88rem;
}
.panel h2 {
  margin: 0 0 0.65rem;
  font-size: 1rem;
}
.split {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 1.15rem;
  align-items: start;
}
.pane {
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fafafa;
  padding: 0.75rem 0.85rem 0.9rem;
  min-height: 0;
}
.edit-pane {
  background: #fff;
}
.preview-pane {
  position: sticky;
  top: 64px;
  max-height: calc(100vh - 80px);
  overflow: auto;
  background: #f7f9fc;
}
.pane-title {
  margin: 0 0 0.5rem;
  font-size: 0.86rem;
  font-weight: 700;
  color: #262626;
}
.pane-hint {
  margin: 0 0 0.45rem;
  font-size: 0.78rem;
  color: #8c8c8c;
}
.block {
  margin-bottom: 0.7rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid #f5f5f5;
}
.block:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}
.block h4 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  color: #8c8c8c;
  font-weight: 700;
}
.basic-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem 0.6rem;
  align-items: start;
}
.basic-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
  font-size: 0.76rem;
  color: #8c8c8c;
  font-weight: 600;
}
.basic-grid input,
.basic-grid textarea {
  font-weight: 500;
  color: #262626;
  font-size: 0.86rem;
  padding: 0.38rem 0.5rem;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  font-family: inherit;
}
.basic-grid .span-2 {
  grid-column: 1 / -1;
}
.basic-grid .basic-logo {
  grid-column: 1 / -1;
}
.basic-grid :deep(.prev) {
  width: 52px;
  height: 52px;
  font-size: 0.7rem;
}
.basic-grid :deep(.hint) {
  display: none;
}
.basic-grid :deep(.lbl) {
  font-size: 0.76rem;
}
.create-block {
  border-bottom: none;
}
.live {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #eef2f7;
  padding: 0.85rem 0.9rem 1rem;
}
.live-head {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 0.65rem;
  margin-bottom: 0.5rem;
}
.live-logo {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  display: grid;
  place-items: center;
  overflow: hidden;
  font-size: 1.1rem;
  font-weight: 700;
  color: #1677ff;
  background: #fafafa;
}
.live-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.live-head h4 {
  margin: 0 0 0.2rem;
  font-size: 1.05rem;
  color: #262626;
}
.live-link {
  color: #1677ff;
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
}
.live-miss {
  margin: 0;
  color: #d9d9d9;
  font-size: 0.78rem;
}
.live-desc {
  margin: 0 0 0.45rem;
  color: #595959;
  font-size: 0.86rem;
  line-height: 1.55;
}
.live-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-bottom: 0.6rem;
}
.live-tags span {
  padding: 2px 8px;
  border-radius: 4px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 0.72rem;
  font-weight: 600;
}
.live-intro {
  border-top: 1px solid #f5f5f5;
  padding-top: 0.65rem;
}
.form.stack {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  max-width: none;
}
@media (max-width: 1100px) {
  .org-console {
    padding: 0.85rem 1rem 1.5rem;
  }
}
@media (max-width: 960px) {
  .split {
    grid-template-columns: 1fr;
  }
  .preview-pane {
    position: static;
    max-height: none;
  }
  .basic-grid {
    grid-template-columns: 1fr;
  }
}
.invite {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  padding: 0.75rem 0.9rem;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  margin-bottom: 1.25rem;
}
.invite code {
  flex: 1;
  min-width: 8rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #262626;
}
.subh {
  margin: 0 0 0.55rem;
  font-size: 0.92rem;
  color: #595959;
}
.scroll {
  max-height: 280px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
.scroll.tall {
  max-height: 320px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
th,
td {
  padding: 0.55rem 0.7rem;
  text-align: left;
  border-bottom: 1px solid #f5f5f5;
}
th {
  position: sticky;
  top: 0;
  background: #fafafa;
  color: #8c8c8c;
  font-weight: 600;
  font-size: 0.78rem;
}
td a {
  color: #1677ff;
  font-weight: 600;
  text-decoration: none;
}
select {
  max-width: 8.5rem;
  font-size: 0.82rem;
}
.form.proj {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem 0.85rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1.1rem;
  border-bottom: 1px solid #f0f0f0;
}
.form.proj .full {
  grid-column: 1 / -1;
}
.empty {
  color: #bfbfbf;
  font-size: 0.9rem;
  padding: 0.5rem 0;
}
.row {
  display: flex;
  gap: 0.4rem;
}
@media (max-width: 640px) {
  .form.proj,
  .preview {
    grid-template-columns: 1fr;
  }
}
</style>
