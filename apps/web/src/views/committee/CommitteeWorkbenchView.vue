<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import ToastFeedback from '@/components/ToastFeedback.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import LiaisonBubble from '@/components/LiaisonBubble.vue'
import LiaisonComposer from '@/components/LiaisonComposer.vue'
import PaperBody from '@/components/PaperBody.vue'
import type { AnnouncementOut, ApplicationOut, ReviewResponse } from '@/api/types'
import { publishedGuide, type GuideBook } from '@/data/publishedGuide'
import { formatDateTime, statusLabel } from '@/utils/statusLabel'

type Tab = 'todo' | 'mail' | 'account' | 'site' | 'settings' | 'roster'
type SiteKind = 'slides' | 'news' | 'guide' | 'pub'
type AccountKind = 'students' | 'mentors' | 'orgs'

type Person = { id: number; name: string; email: string; school?: string | null; disabled: number; orgs: string[] }
type OrgRow = { id: number; name: string; slug: string; admin_email: string; invite_code?: string | null; busy: boolean }
type Talk = { id: number; sender_name: string; body: string; mine: boolean }
type Box = { community_id: number; community_name: string; preview: string; last_id?: number }
type Term = {
  id: number
  community_name: string
  student_name: string
  project_title: string
  reason_label: string
  reason: string
  evidence: string[]
  status: string
  decision_note?: string | null
}
type QueueItem = {
  application_id: number
  title: string
  body?: string | null
  student?: string
  project?: string
  blocks?: Block[]
}
type Slide = {
  id: string
  title: string
  lead: string
  meta: string
  image: string
  primaryLabel: string
  primaryTo: string
  secondaryLabel: string
  secondaryTo: string
  live: boolean
  /** page=点图打开活动页；link=点图去已有地址 */
  jump?: 'page' | 'link'
  link?: string
  pageTitle?: string
  pageBody?: string
  buttonLabel?: string
}
type Block = { id: string; type: 'text' | 'image' | 'video' | 'table'; text?: string; url?: string; rows?: string[][] }
type NewsItem = {
  id: string
  date: string
  title: string
  summary: string
  body: string
  href: string
  live: boolean
  /** news=只发动态；final=同时进入结项公示 */
  kind?: 'news' | 'general' | 'selection' | 'final'
  /** 已经写进站点之后才为真。下拉里换类型不会改这个。 */
  published?: boolean
  announced?: string
  announcementId?: number
  blocks?: Block[]
}
type Chapter = { id: string; title: string; body: string; hidden: boolean; blocks?: Block[] }
type Book = { key: string; title: string; chapters: Chapter[] }

const route = useRoute()
const router = useRouter()
const tabs: { id: Tab; label: string }[] = [
  { id: 'todo', label: '待办' },
  { id: 'roster', label: '结项名单' },
  { id: 'mail', label: '社区来信' },
  { id: 'account', label: '账号' },
  { id: 'site', label: '站点内容' },
  { id: 'settings', label: '平台设置' },
]

const tab = ref<Tab>('todo')
const workKind = ref<'final' | 'case'>('final')
const error = ref('')
const msg = ref('')
const busy = ref(false)
const toast = ref<InstanceType<typeof ToastFeedback> | null>(null)

function note(text: string) {
  error.value = ''
  msg.value = text
  toast.value?.show(text, 'ok')
}

function fail(text: string) {
  error.value = text
  toast.value?.show(text, 'err')
}

const finals = ref<ApplicationOut[]>([])
const finalFilter = ref<'wait' | 'back'>('wait')
const pickedFinal = ref<number | null>(null)
const comment = ref('')
const queue = ref<QueueItem[]>([])

const announcements = ref<AnnouncementOut[]>([])
const pubMode = ref<'draft' | 'live'>('draft')
const pubDraft = ref<{ type: string; title: string; blocks: Block[] } | null>(null)
const openedPub = ref<AnnouncementOut | QueueItem | null>(null)

const boxes = ref<Box[]>([])
const mailId = ref<number | null>(null)
const thread = ref<Talk[]>([])
const mailDraft = ref('')

const cases = ref<Term[]>([])
const caseFilter = ref<'pending' | 'approved' | 'rejected'>('pending')
const caseId = ref<number | null>(null)
const caseNote = ref('')

const accountKind = ref<AccountKind>('students')
const directory = ref<{ students: Person[]; mentors: Person[]; orgs: OrgRow[] }>({
  students: [],
  mentors: [],
  orgs: [],
})
const accountPage = ref(1)
const accountTotal = ref(0)
const accountPageSize = 10
const accountRowsLive = ref<Person[]>([])
const accountQuery = ref('')
const colFilters = ref({ name: '', email: '', org: '', status: '' })
const facets = ref<{ names: string[]; emails: string[]; orgs: string[]; statuses: string[] }>({
  names: [],
  emails: [],
  orgs: [],
  statuses: ['使用中', '已停用'],
})
const pickedAccount = ref<number | null>(null)

const siteKind = ref<SiteKind>('slides')
const slides = ref<Slide[]>([])
const news = ref<NewsItem[]>([])
const books = ref<Book[]>([])
const slideId = ref('')
const newsId = ref('')
const bookKey = ref('')
const chapterId = ref('')

const orgForm = ref({ name: '', slug: '', description: '', admin_name: '', admin_email: '' })
const created = ref('')
const rosterMonth = ref(new Date().toISOString().slice(0, 7))
const roster = ref<{ application_id: number; project_title: string; community_name: string; student_name?: string | null; finished_at?: string | null }[]>([])
const rosterMonths = ref<string[]>([])
const rosterJumped = ref(false)
type CommunityApply = {
  id: number
  name: string
  slug: string
  description?: string | null
  homepage_url?: string | null
  applicant_name?: string | null
  applicant_email?: string | null
  created_at?: string | null
}
const communityApplies = ref<CommunityApply[]>([])
const pickedApplyId = ref<number | null>(null)
const applyNote = ref('')
const pickedApply = computed(() => communityApplies.value.find((item) => item.id === pickedApplyId.value) || null)

async function loadCommunityApplies() {
  const { data } = await api.get<CommunityApply[]>('/committee/community-applications')
  communityApplies.value = data
  if (!data.some((item) => item.id === pickedApplyId.value)) pickedApplyId.value = data[0]?.id ?? null
}

async function reviewCommunity(decision: 'approve' | 'reject') {
  const current = pickedApply.value
  if (!current) return
  if (decision === 'reject' && !applyNote.value.trim()) {
    toast.value?.show('驳回时请写下原因', 'err')
    return
  }
  busy.value = true
  try {
    await api.post(`/communities/${current.id}/review`, {
      decision,
      comment: applyNote.value.trim() || null,
    })
    toast.value?.show(decision === 'approve' ? '已准入该社区' : '已驳回该申请', 'ok')
    applyNote.value = ''
    await loadCommunityApplies()
  } catch (e: unknown) {
    toast.value?.show(e instanceof Error ? e.message : '处理失败', 'err')
  } finally {
    busy.value = false
  }
}

async function loadRoster() {
  const { data } = await api.get<{ items: typeof roster.value; months: string[] }>('/committee/completions', {
    params: { month: rosterMonth.value },
  })
  roster.value = data.items
  rosterMonths.value = data.months
  if (!rosterJumped.value && !data.items.length && data.months.length && data.months[0] !== rosterMonth.value) {
    rosterJumped.value = true
    rosterMonth.value = data.months[0]
    await loadRoster()
  }
}

function readTab(value: unknown): Tab {
  const name = String(value || 'todo')
  if (name === 'publicity') return 'site'
  if (name === 'final' || name === 'case') return 'todo'
  return tabs.some((item) => item.id === name) ? (name as Tab) : 'todo'
}

function openTab(next: Tab) {
  tab.value = next
  void router.replace({ path: '/committee', query: next === 'todo' ? {} : { tab: next } })
}

function openSite(kind: SiteKind) {
  siteKind.value = kind
  if (kind === 'pub') pubMode.value = 'draft'
  openTab('site')
}

const waitingFinals = computed(() =>
  finals.value.filter((item) => !queue.value.some((row) => row.application_id === item.id)),
)
const currentFinal = computed(() => finals.value.find((item) => item.id === pickedFinal.value) || null)
const mentorNote = computed(() => {
  const records = currentFinal.value?.review_records || []
  return [...records].reverse().find((row) => (row.action || '').includes('mentor_final') || row.actor_role === 'mentor')
})
const visibleFinals = computed(() => (finalFilter.value === 'wait' ? waitingFinals.value : finals.value.filter((item) => item.status === 'final_rejected')))
const currentCase = computed(() => cases.value.find((item) => item.id === caseId.value) || null)
const visibleCases = computed(() => cases.value.filter((item) => item.status === caseFilter.value))
const accountPageCount = computed(() => Math.max(1, Math.ceil(accountTotal.value / accountPageSize)))
const currentSlide = computed(() => slides.value.find((item) => item.id === slideId.value) || null)
const currentBox = computed(() => boxes.value.find((item) => item.community_id === mailId.value) || null)
const currentNews = computed(() => news.value.find((item) => item.id === newsId.value) || null)
const draftKind = ref<NonNullable<NewsItem['kind']>>('news')
watch(newsId, () => {
  draftKind.value = currentNews.value?.kind || 'news'
})
const currentBook = computed(() => books.value.find((item) => item.key === bookKey.value) || null)
const currentChapter = computed(
  () => currentBook.value?.chapters.find((item) => item.id === chapterId.value) || null,
)
const counts = computed(() => ({
  final: waitingFinals.value.length,
  pub: queue.value.length,
  mail: boxes.value.length,
  case: cases.value.filter((item) => item.status === 'pending').length,
}))

async function searchAccounts() {
  accountPage.value = 1
  await loadDirectory()
}

function shiftAccount(step: number) {
  const next = accountPage.value + step
  if (next < 1 || next > accountPageCount.value) return
  accountPage.value = next
  void loadDirectory()
}

async function loadFinals() {
  const { data } = await api.get<ApplicationOut[]>('/applications/inbox')
  finals.value = data.filter((item) => item.status === 'committee_final_review' || item.status === 'final_rejected')
  const queued = await api.get<QueueItem[]>('/committee/publicity-queue')
  queue.value = queued.data
}

async function loadPublicity() {
  const { data } = await api.get<AnnouncementOut[]>('/announcements')
  announcements.value = data
}

async function loadMail() {
  const { data } = await api.get<Box[]>('/liaison/committee')
  boxes.value = data
  if (!mailId.value && data[0]) mailId.value = data[0].community_id
  if (mailId.value) await openMail(mailId.value)
}

async function openMail(id: number) {
  mailId.value = id
  const { data } = await api.get<Talk[]>('/liaison/thread', {
    params: { community_id: id, channel: 'committee' },
  })
  thread.value = data
}

async function loadCases() {
  const { data } = await api.get<Term[]>('/liaison/terminations')
  cases.value = data
}

let accountLoadSeq = 0

async function loadFacets(seq = ++accountLoadSeq) {
  const kind = accountKind.value
  const role = kind === 'orgs' ? 'org' : kind === 'mentors' ? 'mentor' : 'student'
  const { data } = await api.get<typeof facets.value>('/committee/directory/facets', { params: { role } })
  if (seq !== accountLoadSeq || accountKind.value !== kind) return
  facets.value = data
}

async function loadDirectory(seq = ++accountLoadSeq) {
  const kind = accountKind.value
  const role = kind === 'orgs' ? 'org' : kind === 'mentors' ? 'mentor' : 'student'
  const { data } = await api.get<{ total: number; rows: Person[] }>('/committee/directory', {
    params: {
      role,
      name: colFilters.value.name,
      email: colFilters.value.email,
      org: kind === 'orgs' ? '' : colFilters.value.org,
      invite: kind === 'orgs' ? colFilters.value.org : '',
      status: colFilters.value.status,
      q: accountQuery.value.trim(),
      page: accountPage.value,
      page_size: accountPageSize,
    },
  })
  if (seq !== accountLoadSeq || accountKind.value !== kind) return
  accountTotal.value = data.total
  accountRowsLive.value = data.rows
  if (accountPage.value > accountPageCount.value) accountPage.value = accountPageCount.value
}

async function loadSite() {
  const [slideRes, newsRes, guideRes] = await Promise.all([
    api.get<{ items: Slide[] }>('/committee/content/slides'),
    api.get<{ items: NewsItem[] }>('/committee/content/news'),
    api.get<{ books: Book[] }>('/committee/content/guide'),
  ])
  slides.value = withHomeSlides(slideRes.data.items || [])
  news.value = ((newsRes.data.items || []).length ? newsRes.data.items : builtinNews()).map((item) => ({
    ...item,
    kind: item.kind || 'news',
    published: true,
  }))
  books.value = usableGuide(guideRes.data.books || [])
  slideId.value = slides.value[0]?.id || ''
  newsId.value = news.value[0]?.id || ''
  bookKey.value = books.value[0]?.key || ''
  chapterId.value = books.value[0]?.chapters[0]?.id || ''
}

async function load() {
  error.value = ''
  await Promise.all([
    loadFinals().catch((e: unknown) => { error.value = e instanceof Error ? e.message : '终审加载失败' }),
    loadPublicity().catch(() => undefined),
    loadMail().catch(() => undefined),
    loadCases().catch(() => undefined),
    loadDirectory().catch(() => undefined),
    loadFacets().catch(() => undefined),
    loadSite().catch(() => undefined),
  ])
}

async function passFinal() {
  const current = currentFinal.value
  if (!current || !mentorNote.value?.comment) return
  queue.value = [
    ...queue.value.filter((item) => item.application_id !== current.id),
    {
      application_id: current.id,
      title: `${current.project_title || '项目'} · ${current.student_name || '学生'}`,
      body: mentorNote.value.comment || '',
      student: current.student_name || '',
      project: current.project_title || '',
    },
  ]
  await api.put('/committee/publicity-queue', { items: queue.value })
  note('已通过终审，进入待公示。公开页还看不到。')
  pickedFinal.value = null
}

async function rejectFinal() {
  const current = currentFinal.value
  if (!current || !comment.value.trim()) {
    error.value = '退回要写原因'
    return
  }
  busy.value = true
  try {
    await api.post<ReviewResponse>(`/applications/${current.id}/final/reviews`, {
      decision: 'reject',
      comment: comment.value.trim(),
      version: current.version,
    })
    note('已退回，社区可以修改后再报')
    comment.value = ''
    await loadFinals()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '退回失败'
  } finally {
    busy.value = false
  }
}

function plainText(blocks: Block[]) {
  return blocks.filter((block) => block.type === 'text').map((block) => (block.text || '').trim()).filter(Boolean).join('\n\n')
}

function encodeBlocks(blocks: Block[]) {
  return JSON.stringify({ blocks, text: plainText(blocks) })
}

function decodeBlocks(body?: string | null): Block[] {
  if (!body) return [{ id: `b-${Date.now()}`, type: 'text', text: '' }]
  try {
    const data = JSON.parse(body) as { blocks?: Block[] }
    if (Array.isArray(data.blocks) && data.blocks.length) return data.blocks
  } catch {
    /* 旧公示是纯文字 */
  }
  return [{ id: `b-${Date.now()}`, type: 'text', text: body }]
}

function startPub() {
  pubMode.value = 'draft'
  openedPub.value = null
  pubDraft.value = {
    type: 'general',
    title: '',
    blocks: [{ id: `b-${Date.now()}`, type: 'text', text: '' }],
  }
}

function openQueue(item: QueueItem) {
  pubDraft.value = null
  if (!item.blocks?.length) item.blocks = decodeBlocks(item.body)
  openedPub.value = item
}

async function publishQueued(item: QueueItem) {
  busy.value = true
  error.value = ''
  try {
    const blocks = item.blocks?.length ? item.blocks : decodeBlocks(item.body)
    const text = plainText(blocks)
    const app = finals.value.find((row) => row.id === item.application_id)
    await api.post(`/applications/${item.application_id}/final/reviews`, {
      decision: 'approve',
      comment: text || item.title,
      version: app?.version,
    })
    const posted = await api.post<{ id: number }>('/announcements', {
      type: 'final',
      title: item.title,
      body: encodeBlocks(blocks),
      application_id: item.application_id,
      is_public: true,
    })
    queue.value = queue.value.filter((row) => row.application_id !== item.application_id)
    await api.put('/committee/publicity-queue', { items: queue.value })
    news.value.unshift({
      id: `n-final-${item.application_id}`,
      date: new Date().toISOString().slice(0, 10),
      title: item.title,
      summary: text.slice(0, 80),
      body: text,
      href: '',
      live: true,
      kind: 'final',
      published: true,
      announcementId: posted.data.id,
      blocks,
    })
    await persistNews()
    openedPub.value = null
    note('已发到最新动态，并单独进入结项公示')
    await Promise.all([loadFinals(), loadPublicity()])
    pubMode.value = 'live'
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '发布失败'
  } finally {
    busy.value = false
  }
}

async function publishManual() {
  const draft = pubDraft.value
  if (!draft?.title.trim()) return
  busy.value = true
  try {
    await api.post('/announcements', {
      type: draft.type,
      title: draft.title.trim(),
      body: encodeBlocks(draft.blocks),
      is_public: true,
    })
    pubDraft.value = null
    note('公示已发布，可在结项公示页打开')
    await loadPublicity()
    pubMode.value = 'live'
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '发布失败'
  } finally {
    busy.value = false
  }
}

async function sendMail(body: string) {
  if (!mailId.value || !body.trim()) return
  const id = mailId.value
  await api.post('/liaison', { community_id: id, channel: 'committee', body })
  note('已发给这个组织')
  const { data } = await api.get<Box[]>('/liaison/committee')
  boxes.value = data
  await openMail(id)
}

async function decide(decision: 'approve' | 'reject') {
  if (!currentCase.value || caseNote.value.trim().length < 2) {
    error.value = '请写明查证结论'
    return
  }
  busy.value = true
  try {
    await api.post(`/liaison/terminations/${currentCase.value.id}`, { decision, note: caseNote.value.trim() })
    caseNote.value = ''
    note(decision === 'approve' ? '已核准终止' : '已驳回')
    await loadCases()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '处理失败'
  } finally {
    busy.value = false
  }
}

async function toggleUser(row: Person) {
  await api.post(`/committee/users/${row.id}/disabled`, { disabled: !row.disabled })
  await loadDirectory()
}

async function toggleOrg(row: Person) {
  try {
    await api.post(`/committee/communities/${row.id}/disabled`, { disabled: !row.disabled })
    await loadDirectory()
  } catch (e: unknown) {
    fail(e instanceof Error ? e.message : '停用失败')
  }
}

const retireOpen = ref(false)
const retireTarget = ref<Person | null>(null)

function retireAccount(row: Person) {
  retireTarget.value = row
  retireOpen.value = true
}

async function confirmRetireAccount() {
  const row = retireTarget.value
  retireTarget.value = null
  if (!row) return
  try {
    const { data } = await api.post<{ status: string }>(`/committee/communities/${row.id}/retire`)
    note(data.status === 'suspended' ? '已停止报名，记录保留' : '已从公开列表移除')
    await loadDirectory()
  } catch (e: unknown) {
    fail(e instanceof Error ? e.message : '处理失败')
  }
}

function builtinSlides(): Slide[] {
  return [
    {
      id: 'intern',
      title: '华科开源原子\n开源实习管理系统',
      lead: '华中科技大学开放原子开源俱乐部面向真实运营场景：社区报名、项目发布、学生申请、三级审核、中选与结项公示。',
      meta: '活动流程全年可演示',
      image: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=80',
      primaryLabel: '查看项目',
      primaryTo: '/projects',
      secondaryLabel: '参与指南',
      secondaryTo: '/guide',
      live: true,
      jump: 'link',
      link: '/projects',
      pageTitle: '华科开源原子',
      pageBody: '',
      buttonLabel: '查看项目',
    },
    {
      id: 'process',
      title: '打通实习全链路\n从申请到结项',
      lead: '组织报名、发布项目、学生申请、导师与组委会审核、结项公示。',
      meta: '学生入口 · 组织入口',
      image: 'https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1800&q=80',
      primaryLabel: '阅读指南',
      primaryTo: '/guide',
      secondaryLabel: '按社区选择',
      secondaryTo: '/projects',
      live: true,
      jump: 'link',
      link: '/guide',
      pageTitle: '打通实习全链路',
      pageBody: '',
      buttonLabel: '参与指南',
    },
    {
      id: 'club',
      title: '连接俱乐部基础设施\n镜像 · 代码仓 · 文档',
      lead: '项目仓库与结项合并请求对接校内代码仓，门户聚合镜像站与公开文档。',
      meta: '薄集成 · 厚运营',
      image: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1800&q=80',
      primaryLabel: '最新动态',
      primaryTo: '/news',
      secondaryLabel: '参与指南',
      secondaryTo: '/guide',
      live: true,
      jump: 'link',
      link: '/news',
      pageTitle: '连接俱乐部基础设施',
      pageBody: '',
      buttonLabel: '最新动态',
    },
  ]
}

function builtinNews(): NewsItem[] {
  return [
    {
      id: 'n-task3',
      date: '2026-03',
      title: '开源实习管理系统进入任务3联调',
      summary: '完成社区、项目和三级审核。',
      body: '完成 JWT 鉴权、社区/项目/三级审核与企业级流水，前端按华科官网风格改版。',
      href: '',
      live: true,
      blocks: [{ id: 'b1', type: 'text', text: '完成 JWT 鉴权、社区/项目/三级审核与企业级流水，前端按华科官网风格改版。' }],
    },
    {
      id: 'n-flow',
      date: '2026-03',
      title: '实习全流程上线',
      summary: '从社区报名到结项公示。',
      body: '社区报名 → 项目发布 → 学生申请 → 三级审核 → 中选公示 → 结项审核。',
      href: '',
      live: true,
      blocks: [{ id: 'b2', type: 'text', text: '社区报名 → 项目发布 → 学生申请 → 三级审核 → 中选公示 → 结项审核。' }],
    },
    {
      id: 'n-club',
      date: '持续更新',
      title: '俱乐部动态请见官网',
      summary: '新闻与镜像站以俱乐部门户为准。',
      body: '新闻、百科、翻译团队与镜像站服务以俱乐部门户为准。',
      href: 'https://hust.openatom.club/',
      live: true,
      blocks: [{ id: 'b3', type: 'text', text: '新闻、百科、翻译团队与镜像站服务以俱乐部门户为准。' }],
    },
  ]
}

function withHomeSlides(saved: Slide[]) {
  const ids = new Set(saved.map((item) => item.id))
  return [...builtinSlides().filter((item) => !ids.has(item.id)), ...saved]
}

function usableGuide(saved: Book[]) {
  const published = publishedGuide() as GuideBook[]
  if (!saved.length || !saved.some((book) => book.key === 'flow')) return published as Book[]
  const rich = saved.some((book) =>
    book.chapters.some((chapter) => (chapter.body || '').trim().length > 80 || (chapter.blocks || []).some((block) => (block.text || '').trim().length > 80 || block.type !== 'text')),
  )
  return rich ? saved : (published as Book[])
}

function syncChapter(chapter: Chapter) {
  const texts = (chapter.blocks || []).filter((block) => block.type === 'text').map((block) => (block.text || '').trim()).filter(Boolean)
  if (texts.length) chapter.body = texts.join('\n\n')
}

function syncNews(item: NewsItem) {
  const texts = (item.blocks || []).filter((block) => block.type === 'text').map((block) => (block.text || '').trim()).filter(Boolean)
  if (texts.length) {
    item.body = texts.join('\n\n')
    item.summary = texts[0].slice(0, 80)
  }
}

const uploading = ref(false)

function ensureBlocks(item: { body?: string | null; blocks?: Block[] }) {
  if (!item.blocks?.length) item.blocks = [{ id: `b-${Date.now()}`, type: 'text', text: item.body || '' }]
  return item.blocks
}

function guideTail() {
  const chapters = currentBook.value?.chapters || []
  return chapters[chapters.length - 1] || null
}

function appendToGuide(kind: 'table' | 'image' | 'video', event?: Event) {
  const chapter = guideTail()
  if (!chapter) return
  if (kind === 'table') addTable(chapter)
  else if (event) void addMedia(chapter, kind, event)
}

function addTable(item: { blocks?: Block[]; body?: string | null; [key: string]: unknown }) {
  item.blocks = item.blocks || []
  item.blocks.push({
    id: `b-${Date.now()}`,
    type: 'table',
    rows: [
      ['', '', ''],
      ['', '', ''],
    ],
  })
}

async function addMedia(
  item: { blocks?: Block[]; body?: string | null; [key: string]: unknown },
  kind: 'image' | 'video',
  event: Event,
) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  error.value = ''
  uploading.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    const { data } = await api.post<{ url: string }>(`/uploads/${kind}`, body)
    item.blocks = item.blocks || []
    item.blocks.push({ id: `b-${Date.now()}`, type: kind, url: data.url })
    note(kind === 'image' ? '图片已放进正文' : '视频已放进正文')
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : '上传失败'
  } finally {
    uploading.value = false
  }
}

const postPreview = ref<{
  kicker: string
  title: string
  blocks: Block[]
  outline: string[]
  sections?: { title: string; blocks: Block[] }[]
} | null>(null)

function openPostPreview(kind: 'news' | 'guide' | 'pub') {
  if (kind === 'guide' && currentBook.value) {
    postPreview.value = {
      kicker: '参与指南',
      title: currentBook.value.title || '未命名',
      blocks: [],
      outline: [],
      sections: currentBook.value.chapters
        .filter((chapter) => !chapter.hidden)
        .map((chapter) => ({ title: chapter.title, blocks: ensureBlocks(chapter) })),
    }
    return
  }
  if (kind === 'news' && currentNews.value) {
    postPreview.value = {
      kicker: currentNews.value.date || '最新动态',
      title: currentNews.value.title || '未命名',
      blocks: ensureBlocks(currentNews.value),
      outline: [],
    }
    return
  }
  if (kind === 'pub' && pubDraft.value) {
    postPreview.value = {
      kicker: pubDraft.value.type === 'selection' ? '中选公示' : '公告',
      title: pubDraft.value.title || '未命名',
      blocks: pubDraft.value.blocks,
      outline: [],
    }
    return
  }
  if (kind === 'pub' && openedPub.value && 'application_id' in openedPub.value) {
    postPreview.value = {
      kicker: '结项公示',
      title: openedPub.value.title || '未命名',
      blocks: ensureBlocks(openedPub.value),
      outline: [],
    }
  }
}

const previewOpen = ref(false)
const previewIndex = ref(0)
const previewSlides = computed(() => {
  const list = slides.value.filter((item) => item.live || item.id === slideId.value)
  return list.length ? list : slides.value
})
const fileRef = ref<HTMLInputElement | null>(null)

async function uploadSlideImage(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (fileRef.value) fileRef.value.value = ''
  if (!file || !currentSlide.value) return
  uploading.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post<{ url: string }>('/uploads/image', fd)
    currentSlide.value.image = data.url
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : '图片上传失败'
  } finally {
    uploading.value = false
  }
}

function openHomePreview() {
  const list = previewSlides.value
  const at = list.findIndex((item) => item.id === slideId.value)
  previewIndex.value = at >= 0 ? at : 0
  previewOpen.value = true
}

function removeSlide(id: string) {
  slides.value = slides.value.filter((item) => item.id !== id)
  if (slideId.value === id) slideId.value = slides.value[0]?.id || ''
}

function addSlide() {
  const liveCount = slides.value.filter((item) => item.live).length
  if (liveCount >= 5) {
    error.value = '展示中最多 5 张，请先下架一张'
    return
  }
  const id = `s-${Date.now()}`
  slides.value.unshift({
    id,
    title: '',
    lead: '',
    meta: '',
    image: '',
    primaryLabel: '了解这次活动',
    primaryTo: `/banner/${id}`,
    secondaryLabel: '',
    secondaryTo: '',
    live: true,
    jump: 'page',
    link: '/projects',
    pageTitle: '新的活动',
    pageBody: '在这里写这次上新要说明的内容。首页只放图片，按钮打开这一页。',
    buttonLabel: '了解这次活动',
  })
  slideId.value = id
}

async function shelveSlide() {
  if (!currentSlide.value) return
  currentSlide.value.live = false
  await saveSlides()
  note('已从首页去掉，对外轮播不再显示这张')
}

async function deleteSlide() {
  if (!currentSlide.value) return
  removeSlide(currentSlide.value.id)
  await saveSlides()
  note('已删除')
}

function addNews() {
  const id = `n-${Date.now()}`
  news.value.unshift({
    id,
    date: new Date().toISOString().slice(0, 10),
    title: '',
    summary: '',
    body: '',
    href: '',
    live: true,
    published: false,
    blocks: [{ id: `${id}-text`, type: 'text', text: '' }],
    kind: 'news',
  })
  newsId.value = id
}

function newsBadge(item: NewsItem) {
  if (!item.published) return '未发布'
  const name = item.kind === 'final' ? '结项公示' : item.kind === 'selection' ? '中选公示' : item.kind === 'general' ? '公告' : '动态'
  return `${name} · ${item.live ? '展示中' : '已下架'}`
}

async function persistNews() {
  await api.put('/committee/content/news', { items: news.value.filter((item) => item.published) })
}

const newsSubmitLabel = computed(() => {
  const posted = !!currentNews.value?.published
  if (draftKind.value === 'final') return posted ? '更新到动态和结项公示' : '发布到动态和结项公示'
  return posted ? '更新' : '发布'
})

const knownPages = ['/completed', '/news', '/projects', '/communities', '/guide']

const buttonGoes = computed({
  get() {
    const slide = currentSlide.value
    if (!slide || slide.jump !== 'link') return 'page'
    return knownPages.includes(slide.link || '') ? slide.link || 'page' : 'custom'
  },
  set(value: string) {
    const slide = currentSlide.value
    if (!slide) return
    if (value === 'page') {
      slide.jump = 'page'
      if (!slide.buttonLabel) slide.buttonLabel = '了解这次活动'
      return
    }
    slide.jump = 'link'
    if (value === 'custom') {
      if (!slide.link || knownPages.includes(slide.link)) slide.link = 'https://'
    } else {
      slide.link = value
      const labels: Record<string, string> = {
        '/completed': '看公示',
        '/news': '最新动态',
        '/projects': '查看项目',
        '/communities': '看社区',
        '/guide': '参与指南',
      }
      if (!slide.buttonLabel || slide.buttonLabel === '了解这次活动') slide.buttonLabel = labels[value] || '前往'
    }
  },
})

const secondGoes = computed({
  get() {
    const slide = currentSlide.value
    if (!slide?.secondaryTo) return ''
    return knownPages.includes(slide.secondaryTo) ? slide.secondaryTo : 'custom'
  },
  set(value: string) {
    const slide = currentSlide.value
    if (!slide) return
    if (!value) {
      slide.secondaryTo = ''
      slide.secondaryLabel = ''
      return
    }
    if (value === 'custom') {
      if (!slide.secondaryTo || knownPages.includes(slide.secondaryTo)) slide.secondaryTo = 'https://'
      if (!slide.secondaryLabel) slide.secondaryLabel = '前往'
      return
    }
    slide.secondaryTo = value
    const labels: Record<string, string> = {
      '/completed': '看公示',
      '/news': '最新动态',
      '/projects': '查看项目',
      '/communities': '看社区',
      '/guide': '参与指南',
    }
    if (!slide.secondaryLabel) slide.secondaryLabel = labels[value] || '前往'
  },
})

async function saveSlides() {
  try {
    for (const item of slides.value) {
      if (item.jump === 'link') {
        item.primaryTo = item.link || item.primaryTo || '/projects'
        item.primaryLabel = item.buttonLabel || item.primaryLabel || '前往'
        item.buttonLabel = item.primaryLabel
      } else {
        item.jump = 'page'
        item.primaryTo = `/banner/${item.id}`
        item.primaryLabel = item.buttonLabel || '了解这次活动'
        item.buttonLabel = item.primaryLabel
      }
    }
    await api.put('/committee/content/slides', { items: slides.value })
    note('已发布到首页')
  } catch (e: unknown) {
    fail(e instanceof Error ? e.message : '发布失败')
  }
}

async function saveNews() {
  const item = currentNews.value
  if (!item) return
  if (!item.title.trim()) {
    fail('请先写标题')
    return
  }
  const wasPublished = !!item.published
  const previousKind = item.kind
  item.kind = draftKind.value
  item.published = true
  try {
    for (const row of news.value) syncNews(row)
    await persistNews()
    if (previousKind === 'final' && item.kind !== 'final' && item.announcementId) {
      await api.delete(`/announcements/${item.announcementId}`)
      item.announcementId = undefined
      item.announced = undefined
      await persistNews()
    }
    if (item.kind === 'final') {
      const mark = `${item.title}\n${encodeBlocks(item.blocks || [])}`
      const body = {
        type: 'final' as const,
        title: item.title,
        body: encodeBlocks(item.blocks || []),
        is_public: true,
      }
      if (item.announcementId) {
        await api.put(`/announcements/${item.announcementId}`, body)
        item.announced = mark
      } else {
        const { data } = await api.post<{ id: number }>('/announcements', body)
        item.announcementId = data.id
        item.announced = mark
        await persistNews()
      }
      note(wasPublished ? '已更新。最新动态和结项公示都换成这一版。' : '已发到最新动态，并单独进入结项公示')
    } else {
      note(wasPublished ? '已更新' : item.kind !== 'news' ? '已作为公示发到最新动态' : '已发布到最新动态')
    }
  } catch (e: unknown) {
    item.kind = previousKind
    item.published = wasPublished
    fail(e instanceof Error ? e.message : '发布失败')
  }
}

async function deleteNews() {
  const item = currentNews.value
  if (!item) return
  const snapshot = news.value.slice()
  const id = item.id
  news.value = news.value.filter((row) => row.id !== id)
  newsId.value = news.value.find((row) => row.id === newsId.value)?.id || news.value[0]?.id || ''
  if (!item.published) {
    note('已删除这条还没发布的稿')
    return
  }
  try {
    await persistNews()
    if (item.kind === 'final') {
      try {
        let announcementId = item.announcementId
        if (!announcementId) {
          const { data } = await api.get<{ id: number; title: string }[]>('/announcements', { params: { type: 'final' } })
          announcementId = data.find((row) => row.title === item.title)?.id
        }
        if (announcementId) await api.delete(`/announcements/${announcementId}`)
      } catch {
        note('动态已删。结项公示那一条没能一起去掉，刷新后再删一次。')
        return
      }
    }
    note('已删除，公开页面不再显示这条')
  } catch (e: unknown) {
    news.value = snapshot
    newsId.value = id
    fail(e instanceof Error ? e.message : '删除失败')
  }
}

function addChapter() {
  const book = currentBook.value
  if (!book) return
  const id = `c-${Date.now()}`
  book.chapters.push({ id, title: '新的一节', body: '', hidden: false, blocks: [{ id: `${id}-text`, type: 'text', text: '' }] })
  chapterId.value = id
}

async function saveGuide() {
  try {
    for (const book of books.value) book.chapters.forEach(syncChapter)
    await api.put('/committee/content/guide', { books: books.value })
    note('参与指南已发布')
  } catch (e: unknown) {
    fail(e instanceof Error ? e.message : '发布失败')
  }
}

async function openOrg() {
  if (!orgForm.value.name.trim() || !orgForm.value.admin_email.trim()) return
  busy.value = true
  try {
    const { data } = await api.post<{
      id: number
      invite_code?: string | null
      admin_initial_password?: string | null
    }>('/communities', {
      name: orgForm.value.name.trim(),
      slug: orgForm.value.slug.trim() || `org-${Date.now()}`,
      description: orgForm.value.description || null,
      admin_name: orgForm.value.admin_name.trim(),
      admin_email: orgForm.value.admin_email.trim(),
    })
    const pw = data.admin_initial_password
      ? `初始密码 ${data.admin_initial_password}（只显示一次，请立刻交给对方）`
      : '该邮箱已有组织账号，未重置密码'
    created.value = `已开通「${orgForm.value.name.trim()}」，社区账号 ${orgForm.value.admin_name || '管理员'} ${orgForm.value.admin_email.trim()}，${pw}。用学生入口选「组织」登录。${data.invite_code ? `导师邀请码 ${data.invite_code}。` : ''}`
    orgForm.value = { name: '', slug: '', description: '', admin_name: '', admin_email: '' }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '开通失败'
  } finally {
    busy.value = false
  }
}

watch(error, (value) => {
  if (value) toast.value?.show(value, 'err')
})

watch(accountKind, () => {
  accountPage.value = 1
  accountQuery.value = ''
  colFilters.value = { name: '', email: '', org: '', status: '' }
  accountRowsLive.value = []
  facets.value = { names: [], emails: [], orgs: [], statuses: ['使用中', '已停用'] }
  const seq = ++accountLoadSeq
  void loadFacets(seq)
  void loadDirectory(seq)
})

watch(
  () => route.query.tab,
  (value) => {
    if (value === 'publicity') siteKind.value = 'news'
    if (value === 'final') workKind.value = 'final'
    if (value === 'case') workKind.value = 'case'
    tab.value = readTab(value)
    if (tab.value === 'roster') void loadRoster().catch(() => undefined)
    if (tab.value === 'todo') void loadCommunityApplies().catch(() => undefined)
  },
  { immediate: true },
)

onMounted(load)
</script>

<template>
  <div class="desk">
    <ToastFeedback ref="toast" />
    <ConfirmDialog
      :open="retireOpen"
      title="停止报名"
      :message="
        retireTarget
          ? `停止报名或移出公开列表。请输入组织全名「${retireTarget.name}」确认。`
          : ''
      "
      :expect-text="retireTarget?.name || ''"
      confirm-text="确认"
      cancel-text="取消"
      danger
      @update:open="retireOpen = $event"
      @cancel="retireTarget = null"
      @confirm="confirmRetireAccount"
    />
    <header class="head">
      <div>
        <h1>组委会</h1>
        <p>待办只处理新社区申请。结项名单用于公示。公示、动态和指南在站点内容里改。</p>
      </div>
    </header>
    <nav class="tabs">
      <button v-for="item in tabs" :key="item.id" type="button" :class="{ on: tab === item.id }" @click="openTab(item.id)">
        {{ item.label }}
      </button>
    </nav>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="msg" class="ok">{{ msg }}</p>

    <section v-if="tab === 'todo'" class="panel work">
      <div class="split">
        <aside>
          <p class="contacts-title">新社区申请 {{ communityApplies.length || '' }}</p>
          <button
            v-for="item in communityApplies"
            :key="item.id"
            type="button"
            class="row"
            :class="{ on: pickedApplyId === item.id }"
            @click="pickedApplyId = item.id"
          >
            <strong>{{ item.name }}</strong>
            <span>{{ item.applicant_name || '申请人未填' }} · {{ item.created_at || '' }}</span>
          </button>
          <p v-if="!communityApplies.length" class="empty">没有待处理的新社区申请。</p>
        </aside>
        <div v-if="pickedApply" class="read">
          <h2>{{ pickedApply.name }}</h2>
          <p class="meta">{{ pickedApply.slug }}</p>
          <p>{{ pickedApply.description || '没有简介。' }}</p>
          <p v-if="pickedApply.homepage_url"><a :href="pickedApply.homepage_url" target="_blank" rel="noopener">{{ pickedApply.homepage_url }}</a></p>
          <p>申请人：{{ pickedApply.applicant_name || '—' }} {{ pickedApply.applicant_email || '' }}</p>
          <label>
            审核意见
            <textarea v-model="applyNote" rows="3" placeholder="驳回时必填原因。通过可以不写。" />
          </label>
          <div class="acts">
            <button class="btn" type="button" :disabled="busy" @click="reviewCommunity('approve')">通过</button>
            <button class="btn danger" type="button" :disabled="busy" @click="reviewCommunity('reject')">驳回</button>
          </div>
        </div>
        <div v-else class="read empty">左边打开一份新社区申请，再决定通过或驳回。</div>
      </div>
    </section>

    <section v-else-if="tab === 'roster'" class="panel work">
      <div class="panel-bar">
        <div>
          <h2>每月结项名单</h2>
          <p>导师验收通过、社区报送后会出现在这里；社区报送时组委会自动接收。按结项月份给公示用。学生奖励材料留在社区。</p>
        </div>
        <label>
          月份
          <input v-model="rosterMonth" type="month" @change="loadRoster" />
        </label>
      </div>
      <p v-if="!roster.length" class="empty">
        这个月还没有结项。
        <template v-if="rosterMonths.length">已有结项在 {{ rosterMonths.join('、') }}。</template>
      </p>
      <ul v-else class="roster">
        <li v-for="item in roster" :key="item.application_id">
          <strong>{{ item.project_title }}</strong>
          <span>{{ item.community_name }} · {{ item.student_name || '学生' }} · {{ item.finished_at || '' }}</span>
        </li>
      </ul>
    </section>

    <section v-else-if="tab === 'mail'" class="panel mail">
      <aside class="contacts">
        <p class="contacts-title">组织</p>
        <button v-for="box in boxes" :key="box.community_id" type="button" class="contact" :class="{ on: mailId === box.community_id }" @click="openMail(box.community_id)">
          <span class="avatar">{{ box.community_name.slice(0, 1) }}</span>
          <span class="who">
            <strong>{{ box.community_name }}</strong>
            <em>{{ box.preview }}</em>
          </span>
        </button>
        <p v-if="!boxes.length" class="empty">还没有组织。</p>
      </aside>
      <div v-if="currentBox" class="chat">
        <header>{{ currentBox.community_name }}</header>
        <div class="log">
          <p v-if="!thread.length" class="empty">还没有对话。先写一句，就会发给这个组织。</p>
          <LiaisonBubble v-for="line in thread" :key="line.id" :body="line.body" :mine="line.mine" :name="line.sender_name" />
        </div>
        <LiaisonComposer placeholder="写给这个组织，可附图片、表格或文件" @send="sendMail" />
      </div>
      <div v-else class="chat empty">先点左边的一个组织，再开始沟通。</div>
    </section>

    <section v-else-if="tab === 'account'" class="panel account">
      <div class="filters">
        <button type="button" :class="{ on: accountKind === 'students' }" @click="accountKind = 'students'">学生</button>
        <button type="button" :class="{ on: accountKind === 'mentors' }" @click="accountKind = 'mentors'">导师</button>
        <button type="button" :class="{ on: accountKind === 'orgs' }" @click="accountKind = 'orgs'">组织</button>
      </div>
      <div class="account-bar">
        <input v-model="accountQuery" type="search" placeholder="输入姓名、邮箱或组织，回车查找" @keyup.enter="searchAccounts" />
        <button class="btn" type="button" @click="searchAccounts">查找</button>
        <span>共 {{ accountTotal }} 条</span>
      </div>
      <div class="task-scroll">
        <table class="task-table">
          <thead>
            <tr>
              <th>
                <label class="col-filter" :class="{ on: colFilters.name }">
                  {{ accountKind === 'orgs' ? '组织' : '姓名' }}
                  <select v-model="colFilters.name" @change="searchAccounts" :aria-label="accountKind === 'orgs' ? '按组织筛选' : '按姓名筛选'">
                    <option value="">全部</option>
                    <option v-for="item in facets.names" :key="item" :value="item">{{ item }}</option>
                  </select>
                </label>
              </th>
              <th>
                <label class="col-filter" :class="{ on: colFilters.email }">
                  {{ accountKind === 'orgs' ? '管理员邮箱' : '邮箱' }}
                  <select v-model="colFilters.email" @change="searchAccounts" aria-label="按邮箱筛选">
                    <option value="">全部</option>
                    <option v-for="item in facets.emails" :key="item" :value="item">{{ item }}</option>
                  </select>
                </label>
              </th>
              <th>
                <label class="col-filter" :class="{ on: colFilters.org }">
                  {{ accountKind === 'orgs' ? '邀请码' : '所属' }}
                  <select v-model="colFilters.org" @change="searchAccounts" :aria-label="accountKind === 'orgs' ? '按邀请码筛选' : '按所属筛选'">
                    <option value="">全部</option>
                    <option v-for="item in facets.orgs" :key="item" :value="item">{{ item }}</option>
                  </select>
                </label>
              </th>
              <th>
                <label class="col-filter" :class="{ on: colFilters.status }">
                  状态
                  <select v-model="colFilters.status" @change="searchAccounts" aria-label="按状态筛选">
                    <option value="">全部</option>
                    <option value="active">使用中</option>
                    <option value="disabled">已停用</option>
                  </select>
                </label>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in accountRowsLive" :key="row.id">
              <td>{{ row.name }}</td>
              <td>{{ row.email || '—' }}</td>
              <td>{{ row.orgs.filter(Boolean).join('、') || '—' }}</td>
              <td>{{ row.disabled ? '已停用' : '使用中' }}</td>
              <td>
                <button v-if="accountKind !== 'orgs'" class="manage-link" type="button" @click="toggleUser(row)">
                  {{ row.disabled ? '恢复' : '停用' }}
                </button>
                <template v-else>
                  <button class="manage-link" type="button" @click="toggleOrg(row)">
                    {{ row.disabled ? '恢复' : '停用' }}
                  </button>
                  <button class="manage-link" type="button" @click="retireAccount(row)">停止报名</button>
                </template>
              </td>
            </tr>
            <tr v-if="!accountRowsLive.length">
              <td colspan="5" class="empty">没有符合条件的账号。换一个关键词，或翻页再查。</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pager">
        <span>共 {{ accountTotal }} 条 · 第 {{ accountPage }} / {{ accountPageCount }} 页</span>
        <button type="button" :disabled="accountPage <= 1" @click="shiftAccount(-1)">上一页</button>
        <button type="button" :disabled="accountPage >= accountPageCount" @click="shiftAccount(1)">下一页</button>
      </div>
    </section>

    <section v-else-if="tab === 'site'" class="panel site">
      <p class="howto">先选要改的页面，再改右边的文字。预览和访客看到的是同一块内容。满意后点底部的发布，公开页才会换成新的。</p>
      <div class="filters">
        <button type="button" :class="{ on: siteKind === 'slides' }" @click="siteKind = 'slides'">首页大图</button>
        <button type="button" :class="{ on: siteKind === 'news' }" @click="siteKind = 'news'; openedPub = null">最新动态</button>
        <button type="button" :class="{ on: siteKind === 'guide' }" @click="siteKind = 'guide'">参与指南</button>
      </div>
      <div class="split">
        <aside>
          <template v-if="siteKind === 'slides'">
            <button class="side-add" type="button" @click="addSlide">新增大图</button>
            <button v-for="item in slides" :key="item.id" type="button" class="row" :class="{ on: slideId === item.id }" @click="slideId = item.id">
              <strong>{{ item.pageTitle || item.title || '未命名大图' }}</strong>
              <span>{{ item.live ? '展示中' : '已下架' }}</span>
            </button>
          </template>
          <template v-else-if="siteKind === 'news'">
            <button class="side-add" type="button" @click="openedPub = null; addNews()">写一条</button>
            <button v-for="item in queue" :key="item.application_id" type="button" class="row" :class="{ on: openedPub === item }" @click="newsId = ''; openQueue(item)">
              <strong>{{ item.title }}</strong>
              <span>结项草稿</span>
            </button>
            <button v-for="item in news" :key="item.id" type="button" class="row" :class="{ on: newsId === item.id && openedPub == null }" @click="openedPub = null; newsId = item.id">
              <strong>{{ item.title || '未命名' }}</strong>
              <span>{{ newsBadge(item) }}</span>
            </button>
          </template>
          <template v-else-if="siteKind === 'pub'">
            <div class="filters">
              <button type="button" :class="{ on: pubMode === 'draft' }" @click="pubMode = 'draft'; pubDraft = null; openedPub = null">待编写</button>
              <button type="button" :class="{ on: pubMode === 'live' }" @click="pubMode = 'live'; pubDraft = null; openedPub = null">已发布</button>
            </div>
            <button v-if="pubMode === 'draft'" class="side-add" type="button" @click="startPub">写一条公示</button>
            <template v-if="pubMode === 'draft'">
              <button v-for="item in queue" :key="item.application_id" type="button" class="row" :class="{ on: openedPub === item }" @click="openQueue(item)">
                <strong>{{ item.title }}</strong>
                <span>结项草稿</span>
              </button>
              <p v-if="!queue.length && !pubDraft" class="empty">终审通过后会出现草稿，也可以直接写一条公示。</p>
            </template>
            <template v-else>
              <button v-for="item in announcements" :key="item.id" type="button" class="row" :class="{ on: openedPub === item }" @click="pubDraft = null; openedPub = item">
                <strong>{{ item.title }}</strong>
                <span>{{ item.type === 'final' ? '结项' : item.type === 'selection' ? '中选' : '公告' }}</span>
              </button>
              <p v-if="!announcements.length" class="empty">还没有已发布的公示。</p>
            </template>
          </template>
          <template v-else>
            <button v-for="book in books" :key="book.key" type="button" class="row" :class="{ on: bookKey === book.key }" @click="bookKey = book.key">
              <strong>{{ book.title }}</strong>
            </button>
          </template>
        </aside>
        <div class="read site-work">
          <form v-if="siteKind === 'slides' && currentSlide" class="hero-desk" @submit.prevent="saveSlides">
            <section class="hero-visual">
              <img v-if="currentSlide.image" :src="currentSlide.image" alt="" />
              <div v-else class="upload-empty">还没有图片</div>
              <input ref="fileRef" type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden @change="uploadSlideImage" />
              <button class="btn" type="button" :disabled="uploading" @click="fileRef?.click()">
                {{ uploading ? '上传中…' : currentSlide.image ? '更换图片' : '上传图片' }}
              </button>
              <p class="meta">JPG / PNG / WebP / GIF，最大 5MB</p>
            </section>
            <label>图上的标题（可不填）<textarea v-model="currentSlide.title" rows="3" /></label>
            <label>图上的一句说明（可不填）<textarea v-model="currentSlide.lead" rows="3" /></label>
            <label>按钮上的字<input v-model="currentSlide.buttonLabel" placeholder="例如：了解这次活动" /></label>
            <label>这个按钮打开
              <select v-model="buttonGoes">
                <option value="page">这次新写的活动页</option>
                <option value="/completed">结项公示</option>
                <option value="/news">最新动态</option>
                <option value="/projects">查看项目</option>
                <option value="/communities">社区</option>
                <option value="/guide">参与指南</option>
                <option value="custom">自己填一个网址</option>
              </select>
            </label>
            <template v-if="buttonGoes === 'page'">
              <label>活动页标题<input v-model="currentSlide.pageTitle" /></label>
              <label>活动页正文<textarea v-model="currentSlide.pageBody" rows="4" /></label>
            </template>
            <label v-else-if="buttonGoes === 'custom'" class="span-2">按钮网址<input v-model="currentSlide.link" placeholder="https:// 或 /projects" /></label>
            <label>再放一个按钮
              <select v-model="secondGoes">
                <option value="">不放</option>
                <option value="/completed">结项公示</option>
                <option value="/news">最新动态</option>
                <option value="/projects">查看项目</option>
                <option value="/communities">社区</option>
                <option value="/guide">参与指南</option>
                <option value="custom">自己填一个网址</option>
              </select>
            </label>
            <label v-if="secondGoes && secondGoes !== 'custom'">第二个按钮上的字<input v-model="currentSlide.secondaryLabel" placeholder="例如：看公示" /></label>
            <label v-else-if="secondGoes === 'custom'">第二个按钮的网址<input v-model="currentSlide.secondaryTo" placeholder="https:// 或 /communities" /></label>
            <div class="hero-acts">
              <button class="btn" type="submit">发布到首页</button>
              <button class="btn ghost" type="button" @click="openHomePreview">预览首页</button>
              <button class="btn ghost" type="button" @click="shelveSlide">从首页去掉</button>
              <button class="btn ghost" type="button" @click="deleteSlide">删除这条</button>
            </div>
          </form>
          <form v-else-if="siteKind === 'news' && currentNews && !(openedPub && 'application_id' in openedPub)" class="paper" @submit.prevent="saveNews">
            <div class="paper-frame">
            <select v-model="draftKind" class="paper-kind">
              <option value="news">最新动态</option>
              <option value="general">公告</option>
              <option value="selection">中选公示</option>
              <option value="final">结项公示</option>
            </select>
            <p v-if="draftKind === 'final'" class="meta">确定后会出现在最新动态，并单独进入结项公示。</p>
            <input v-model="currentNews.title" class="paper-title" required placeholder="标题" />
            <PaperBody :host="currentNews" />
            </div>
            <div class="paper-tools">
              <button type="button" @click="addTable(currentNews)">插入表格</button>
              <label>插入图片<input class="file" type="file" accept="image/jpeg,image/png,image/webp,image/gif" @change="addMedia(currentNews, 'image', $event)" /></label>
              <label>插入视频<input class="file" type="file" accept="video/mp4,video/webm" @change="addMedia(currentNews, 'video', $event)" /></label>
              <button type="button" @click="openPostPreview('news')">预览</button>
            </div>
            <div class="acts">
              <label class="check"><input v-model="currentNews.live" type="checkbox" /> 在最新动态展示</label>
              <button class="btn" type="submit">{{ newsSubmitLabel }}</button>
              <button class="btn ghost" type="button" @click="deleteNews">删除</button>
            </div>
          </form>
          <form v-else-if="siteKind === 'guide' && currentBook" class="paper" @submit.prevent="saveGuide">
            <div class="paper-frame">
            <input v-model="currentBook.title" class="paper-title" placeholder="这篇指南的标题" />
            <section v-for="chapter in currentBook.chapters" :key="chapter.id" class="guide-piece">
              <input v-model="chapter.title" class="piece-title" placeholder="这一段的小标题，可空" />
              <PaperBody :host="chapter" />
            </section>
            </div>
            <div class="paper-tools">
              <button type="button" @click="addChapter">加一段小标题</button>
              <button type="button" @click="appendToGuide('table')">插入表格</button>
              <label>插入图片<input class="file" type="file" accept="image/jpeg,image/png,image/webp,image/gif" @change="appendToGuide('image', $event)" /></label>
              <label>插入视频<input class="file" type="file" accept="video/mp4,video/webm" @change="appendToGuide('video', $event)" /></label>
              <button type="button" @click="openPostPreview('guide')">预览全文</button>
            </div>
            <div class="acts">
              <button class="btn" type="submit">发布整篇指南</button>
            </div>
          </form>
          <form v-else-if="siteKind === 'pub' && pubDraft" class="paper" @submit.prevent="publishManual">
            <div class="paper-frame">
            <select v-model="pubDraft.type" class="paper-kind">
              <option value="general">公告</option>
              <option value="selection">中选公示</option>
            </select>
            <input v-model="pubDraft.title" class="paper-title" required placeholder="标题" />
            <PaperBody :host="pubDraft" />
            </div>
            <div class="paper-tools">
              <button type="button" @click="addTable(pubDraft)">插入表格</button>
              <label>插入图片<input class="file" type="file" accept="image/jpeg,image/png,image/webp,image/gif" @change="addMedia(pubDraft, 'image', $event)" /></label>
              <label>插入视频<input class="file" type="file" accept="video/mp4,video/webm" @change="addMedia(pubDraft, 'video', $event)" /></label>
              <button type="button" @click="openPostPreview('pub')">预览</button>
            </div>
            <div class="acts">
              <button class="btn" type="submit" :disabled="busy">发布到公示</button>
            </div>
          </form>
          <div v-else-if="(siteKind === 'news' || siteKind === 'pub') && openedPub && 'application_id' in openedPub" class="paper">
            <div class="paper-frame">
            <p class="paper-kicker">结项公示</p>
            <input v-model="openedPub.title" class="paper-title" placeholder="标题" />
            <PaperBody :host="openedPub" />
            </div>
            <div class="paper-tools">
              <button type="button" @click="addTable(openedPub as QueueItem)">插入表格</button>
              <label>插入图片<input class="file" type="file" accept="image/jpeg,image/png,image/webp,image/gif" @change="addMedia(openedPub as QueueItem, 'image', $event)" /></label>
              <label>插入视频<input class="file" type="file" accept="video/mp4,video/webm" @change="addMedia(openedPub as QueueItem, 'video', $event)" /></label>
              <button type="button" @click="openPostPreview('pub')">预览</button>
            </div>
            <div class="acts">
              <button class="btn" type="button" :disabled="busy" @click="publishQueued(openedPub as QueueItem)">发布到结项公示</button>
            </div>
          </div>
          <article v-else-if="siteKind === 'pub' && openedPub && 'published_at' in openedPub" class="news-preview">
            <strong>{{ openedPub.title }}</strong>
            <template v-for="block in decodeBlocks(openedPub.body)" :key="block.id">
              <p v-if="block.type === 'text'">{{ block.text }}</p>
              <img v-else-if="block.type === 'image' && block.url" :src="block.url" alt="" />
              <table v-else-if="block.type === 'table'" class="paper-table">
                <tr v-for="(row, ri) in block.rows" :key="ri"><td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td></tr>
              </table>
              <video v-else-if="block.url" :src="block.url" controls />
            </template>
          </article>
          <p v-else-if="siteKind === 'pub'" class="empty">左边写一条公示，或打开终审留下的草稿。</p>
          <p v-else class="empty">左边选一节，就能在右边写下正文。</p>
        </div>
      </div>
    </section>

    <section v-else class="panel settings">
      <article>
        <h2>开通组织</h2>
        <p>开通后会同时创建该社区的组织账号，用来收学生的奖励申请。系统会生成一次性随机初始密码（只显示一次），从学生入口选「组织」登录。</p>
        <form class="stack" @submit.prevent="openOrg">
          <input v-model="orgForm.name" placeholder="组织名称" required />
          <input v-model="orgForm.slug" placeholder="英文标识，可空" />
          <input v-model="orgForm.description" placeholder="一句简介" />
          <input v-model="orgForm.admin_name" placeholder="管理员姓名" />
          <input v-model="orgForm.admin_email" type="email" placeholder="管理员邮箱" required />
          <button class="btn" type="submit" :disabled="busy">开通</button>
        </form>
        <p v-if="created">{{ created }}</p>
      </article>
      <article>
        <h2>学生平台绑定</h2>
        <p>配置 GitHub、Gitee、GitCode、GitLink 和俱乐部 Gitea。不影响终审和公示。</p>
        <RouterLink class="btn" to="/committee/oauth">进入绑定配置</RouterLink>
      </article>
    </section>
  </div>

  <div v-if="postPreview" class="home-modal" @click.self="postPreview = null">
    <div class="home-page post-sheet" role="dialog" aria-label="文章预览">
      <div class="preview-bar">
        <strong>预览 · 访客看到的文章</strong>
        <button type="button" class="close" @click="postPreview = null">关闭</button>
      </div>
      <div class="post-layout">
        <aside v-if="postPreview.outline.length">
          <p>{{ postPreview.kicker }}</p>
          <span v-for="name in postPreview.outline" :key="name" :class="{ on: name === postPreview.title }">{{ name }}</span>
        </aside>
        <article>
          <p class="post-kicker">{{ postPreview.kicker }}</p>
          <h1>{{ postPreview.title }}</h1>
          <template v-if="postPreview.sections?.length">
            <section v-for="section in postPreview.sections" :key="section.title" class="post-section">
              <h2>{{ section.title }}</h2>
              <template v-for="block in section.blocks" :key="block.id">
                <p v-if="block.type === 'text'">{{ block.text }}</p>
                <img v-else-if="block.type === 'image' && block.url" :src="block.url" alt="" />
                <table v-else-if="block.type === 'table'" class="paper-table">
                  <tr v-for="(row, ri) in block.rows" :key="ri"><td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td></tr>
                </table>
                <video v-else-if="block.url" :src="block.url" controls />
              </template>
            </section>
          </template>
          <template v-else v-for="block in postPreview.blocks" :key="block.id">
            <p v-if="block.type === 'text'">{{ block.text }}</p>
            <img v-else-if="block.type === 'image' && block.url" :src="block.url" alt="" />
            <table v-else-if="block.type === 'table'" class="paper-table">
              <tr v-for="(row, ri) in block.rows" :key="ri"><td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td></tr>
            </table>
            <video v-else-if="block.url" :src="block.url" controls />
          </template>
        </article>
      </div>
    </div>
  </div>

  <div v-if="previewOpen" class="home-modal" @click.self="previewOpen = false">
    <div class="home-page" role="dialog" aria-label="首页预览">
      <div class="preview-bar">
        <strong>首页预览</strong>
        <button type="button" class="close" @click="previewOpen = false">关闭</button>
      </div>
      <header class="topnav">
        <div class="topnav-inner">
          <span class="brand">
            <img src="/logos/penguin-blue.svg" alt="" />
            <span><strong>华科开源原子</strong><small>开源实习管理系统</small></span>
          </span>
          <nav>
            <span>首页</span><span>查看项目</span><span>结项公示</span><span>最新动态</span><span>参与指南</span>
          </nav>
        </div>
      </header>
      <section class="hero-carousel preview-hero">
        <div
          v-for="(s, i) in previewSlides"
          :key="s.id"
          class="hero-slide"
          :class="{ active: i === previewIndex }"
          :style="{ backgroundImage: s.image ? `linear-gradient(105deg, rgba(8,12,20,.82) 0%, rgba(15,23,42,.45) 55%, rgba(15,23,42,.25) 100%), url(${s.image})` : 'linear-gradient(105deg, #1e293b, #0f172a)' }"
        >
          <div class="hero-inner">
            <h1>{{ s.title || s.pageTitle || '首页大图' }}</h1>
            <p v-if="s.lead" class="hero-lead">{{ s.lead }}</p>
            <div class="hero-cta">
              <span class="btn ghost">{{ s.buttonLabel || s.primaryLabel || '了解这次活动' }}</span>
              <span v-if="s.secondaryLabel" class="btn ghost">{{ s.secondaryLabel }}</span>
            </div>
          </div>
        </div>
        <button v-if="previewSlides.length > 1" class="hero-nav prev" type="button" @click="previewIndex = (previewIndex + previewSlides.length - 1) % previewSlides.length">‹</button>
        <button v-if="previewSlides.length > 1" class="hero-nav next" type="button" @click="previewIndex = (previewIndex + 1) % previewSlides.length">›</button>
        <div class="hero-dots">
          <button v-for="(s, i) in previewSlides" :key="s.id" type="button" class="hero-dot" :class="{ active: i === previewIndex }" @click="previewIndex = i" />
        </div>
      </section>
      <section class="section">
        <div class="value-grid">
          <div class="value-item"><div class="value-glyph">项</div><h3>零距离参与开源课题</h3><p>对接俱乐部多 SIG / 社区项目，在真实仓库完成贡献</p></div>
          <div class="value-item"><div class="value-glyph">导</div><h3>导师一对一指导</h3><p>申请、审核、结项全流程留痕，沟通可追溯</p></div>
          <div class="value-item"><div class="value-glyph">审</div><h3>三级审核与公示</h3><p>导师、社区、组委会节点清晰，中选与结项公开透明</p></div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.desk { width: 100%; padding: 0.85rem 1.75rem 2rem; box-sizing: border-box; background: #f5f7fb; min-height: calc(100vh - 64px); }
.head h1 { margin: 0; font-size: 1.45rem; color: #1e3a5f; }
.head p { margin: 0.25rem 0 0; color: #64748b; }
.tabs { display: flex; gap: 0; border-bottom: 1px solid #d9d9d9; margin: 14px 0 0; overflow-x: auto; }
.tabs button { border: 0; background: transparent; padding: 0.7rem 1rem; color: #64748b; cursor: pointer; font: inherit; border-bottom: 2px solid transparent; }
.tabs button.on { color: #1677ff; font-weight: 700; border-bottom-color: #1677ff; }
.panel { background: #fff; border: 1px solid #d9d9d9; border-top: 0; border-radius: 0 0 10px 10px; min-height: 560px; }
.todos { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 16px; }
.todos button { border: 1px solid #d6deea; background: #f7f9fc; border-radius: 10px; padding: 18px; text-align: left; cursor: pointer; font: inherit; }
.todos b { display: block; font-size: 1.4rem; color: #1e3a5f; }
.work > .filters { padding: 12px 12px 0; }
.split { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 640px; }
.work > .filters { padding: 12px 12px 0; }
.work > .split { min-height: 600px; }
aside { border-right: 1px solid #e5e7eb; padding: 12px; background: #f7f9fc; overflow: auto; }
.read { padding: 16px 18px; }
.filters { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.filters button, .btn.sm { border: 1px solid #c5d0e0; background: #fff; border-radius: 999px; padding: 4px 10px; cursor: pointer; font: inherit; }
.filters button.on { background: #1677ff; color: #fff; border-color: #1677ff; }
.row { display: block; width: 100%; text-align: left; border: 1px solid #d6deea; background: #fff; border-radius: 8px; padding: 10px; margin: 0 0 8px; cursor: pointer; font: inherit; }
.row.on { border-color: #1677ff; box-shadow: inset 3px 0 0 #1677ff; background: #e8f3ff; }
.row span, .meta, .empty { display: block; color: #64748b; font-size: 0.82rem; }
article { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
textarea, input, select { width: 100%; box-sizing: border-box; border: 1px solid #c5d0e0; border-radius: 8px; padding: 8px 10px; font: inherit; margin: 6px 0; }
.acts { display: flex; gap: 8px; }
.btn { background: #1677ff; color: #fff; border: 0; border-radius: 8px; padding: 8px 14px; cursor: pointer; font: inherit; }
.btn.danger { background: #dc2626; }
.stack { display: flex; flex-direction: column; align-items: flex-start; }
.account { padding: 16px; }
.account-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.account-bar input { max-width: 320px; margin: 0; }
.account-field { width: auto; min-width: 8.5rem; margin: 0; }
.account-bar span { color: #8c8c8c; font-size: 0.85rem; }
.task-scroll { overflow: auto; border: 1px solid #eee; border-radius: 10px; }
.task-table { width: 100%; border-collapse: collapse; }
.task-table th { background: #fafafa; text-align: left; font-size: 0.8rem; color: #8c8c8c; padding: 0.7rem 0.9rem; white-space: nowrap; }
.col-filter { display: inline-flex; flex-direction: row; flex-wrap: nowrap; align-items: center; gap: 2px; color: #8c8c8c; font-weight: 650; white-space: nowrap; }
.task-table th .col-filter select { width: 1.1rem; min-width: 1.1rem; max-width: 1.1rem; height: 1.1rem; flex: 0 0 1.1rem; margin: 0; padding: 0; border: 0; border-radius: 0; background: transparent; color: #8c8c8c; cursor: pointer; }
.col-filter.on { color: #1677ff; }
.col-filter.on select { color: #1677ff; }
.task-table td { padding: 0.85rem 0.9rem; border-top: 1px solid #f5f5f5; }
.manage-link { border: 0; background: none; color: #1677ff; cursor: pointer; font: inherit; padding: 0; }
.manage-link + .manage-link { margin-left: 12px; }
.pager { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.pager button { border: 1px solid #d9d9d9; background: #fff; border-radius: 6px; padding: 4px 10px; font: inherit; cursor: pointer; }
.home-modal { position: fixed; inset: 0; z-index: 3000; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; padding: 28px 16px; }
.home-page { width: min(880px, 100%); max-height: min(86vh, 640px); overflow: auto; background: #fff; border-radius: 14px; box-shadow: 0 18px 48px rgba(15, 23, 42, 0.28); }
.preview-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid #e5e7eb; background: #f8fafc; border-radius: 14px 14px 0 0; position: sticky; top: 0; z-index: 2; }
.preview-bar strong { color: #1e3a5f; font-size: 0.92rem; }
.home-page .topnav { position: static; background: #fff; }
.home-modal :deep(.preview-hero),
.home-modal :deep(.hero-slide.active) { min-height: 240px; }
.home-page .brand { display: flex; align-items: center; gap: 8px; }
.home-page .brand img { width: 28px; height: 28px; }
.home-page .brand strong, .home-page .brand small { display: block; line-height: 1.15; }
.home-page .brand small { font-size: 0.72rem; color: #64748b; }
.home-page .topnav-inner { display: flex; align-items: center; gap: 16px; }
.home-page nav { display: flex; gap: 14px; color: #334155; font-size: 0.9rem; margin-left: auto; }
.close { border: 0; background: #1677ff; color: #fff; border-radius: 8px; padding: 6px 12px; cursor: pointer; font: inherit; }
.preview-hero { min-height: min(72vh, 560px); }
.site { padding: 16px; }
.side-add { display: block; width: 100%; margin-bottom: 8px; border: 1px dashed #1677ff; background: #f0f7ff; color: #1677ff; border-radius: 8px; padding: 8px 10px; font: inherit; font-weight: 650; cursor: pointer; text-align: left; }
.site-work { display: block; }
.hero-desk { display: grid; grid-template-columns: 260px minmax(0, 1fr) minmax(0, 1fr); gap: 14px 16px; width: 100%; align-items: start; }
.hero-visual { grid-column: 1; grid-row: 1 / span 6; display: flex; flex-direction: column; gap: 8px; }
.hero-visual img, .hero-visual .upload-empty { width: 100%; height: 220px; object-fit: cover; border-radius: 10px; }
.hero-desk > label { display: flex; flex-direction: column; gap: 4px; color: #64748b; font-size: 0.82rem; min-width: 0; }
.hero-desk .span-2 { grid-column: span 2; }
.hero-acts { grid-column: 2 / -1; display: flex; gap: 8px; flex-wrap: wrap; align-self: end; }
.paper-table { width: 100%; border-collapse: collapse; margin: 6px 0; }
.paper-table td { border: 1px solid #d0d7e2; padding: 0; }
.paper-table input { border: 0; border-radius: 0; margin: 0; padding: 6px 8px; width: 100%; background: transparent; box-shadow: none; }
.table-op { border: 0; background: transparent; color: #1677ff; cursor: pointer; font: inherit; padding: 0 8px 4px 0; }
.outline { margin-top: 12px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
.paper { width: 100%; margin: 0; padding: 0 0 12px; }
.paper-frame { height: min(62vh, 560px); overflow-y: scroll; overflow-x: hidden; border: 1px solid #d0d7e2; border-radius: 12px; background: #fff; padding: 12px 18px 16px; }
.paper-frame::-webkit-scrollbar { width: 10px; }
.paper-frame::-webkit-scrollbar-thumb { background: #c5d0e0; border-radius: 8px; }
.paper-frame::-webkit-scrollbar-track { background: #f4f7fb; }
.paper-kicker, .paper-kicker-input { margin: 0 0 4px; color: #64748b; font-size: 0.85rem; }
.paper-frame input.paper-kicker-input { border: 0; border-radius: 0; padding: 0; margin: 0; width: 100%; background: transparent; box-shadow: none; }
.paper-frame select.paper-kind { width: auto; margin: 0 0 8px; }
.paper-frame input.paper-title { border: 0; border-bottom: 1px solid #eef2f6; border-radius: 0; box-shadow: none; font-size: 1.7rem; font-weight: 700; color: #1e3a5f; padding: 4px 0 10px; margin: 0 0 8px; background: transparent; }
.paper-frame input.paper-title:focus { outline: none; border-bottom-color: #1677ff; }
.guide-piece + .guide-piece { border-top: 1px solid #eef2f6; margin-top: 18px; padding-top: 14px; }
.paper-frame input.piece-title { border: 0; background: transparent; box-shadow: none; border-radius: 0; font-size: 1.15rem; font-weight: 700; color: #1e3a5f; padding: 4px 0; margin: 6px 0 0; }
.paper-block { position: relative; margin: 0; }
.paper-frame textarea.paper-text { border: 0; border-radius: 0; box-shadow: none; background: transparent; min-height: 3.2rem; resize: none; line-height: 1.85; font-size: 1.02rem; padding: 6px 0; margin: 0; }
.paper-frame textarea.paper-text:focus { outline: none; }
.paper-frame img, .paper-frame video { display: block; width: min(100%, 720px); max-height: 220px; object-fit: contain; background: #f7f9fc; border-radius: 8px; margin: 8px 0; }
.paper-media { cursor: pointer; }
.table-wrap.pick { padding: 8px 8px 2px; }
.pick { border-radius: 8px; }
.pick.on, .pick:focus { outline: 2px solid #1677ff; outline-offset: 3px; }
.paper-tools { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 0 16px; border-top: 1px solid #eef2f6; }
.paper-tools button, .paper-tools label { border: 1px solid #d0d7e2; background: #fff; border-radius: 999px; padding: 6px 12px; cursor: pointer; font: inherit; color: #1e3a5f; }
.post-sheet { width: min(980px, 100%); }
.post-layout { display: block; }
.post-layout:has(aside) { display: grid; grid-template-columns: 220px minmax(0, 1fr); }
.post-layout aside { border-right: 1px solid #eef2f6; padding: 16px 12px; background: #f8fafc; }
.post-layout aside p { margin: 0 0 8px; font-weight: 700; color: #1e3a5f; }
.post-layout aside span { display: block; padding: 6px 8px; color: #64748b; font-size: 0.86rem; }
.post-layout aside span.on { color: #1677ff; background: #e8f3ff; border-radius: 6px; }
.post-layout article { width: 100%; max-width: 760px; padding: 28px 36px 40px; box-sizing: border-box; }
.post-kicker { margin: 0; color: #64748b; }
.post-layout h1 { margin: 0.3rem 0 1rem; color: #1e3a5f; font-size: 1.8rem; }
.post-section { margin: 0 0 1.2rem; }
.post-section h2 { margin: 1.2rem 0 0.4rem; font-size: 1.15rem; color: #1e3a5f; }
.post-layout article p { line-height: 1.85; white-space: pre-wrap; }
.post-layout article img, .post-layout article video { display: block; width: min(100%, 720px); max-height: 280px; object-fit: contain; border-radius: 8px; margin: 12px 0; background: #f7f9fc; }
.btn.ghost { background: #fff; color: #1e3a5f; border: 1px solid #d0d7e2; }
.upload-row { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }
.upload-row img, .upload-empty { width: 160px; height: 90px; object-fit: cover; border-radius: 8px; background: #eef3f9; border: 1px solid #d6deea; }
.upload-empty { display: flex; align-items: center; justify-content: center; color: #8c8c8c; font-size: 0.82rem; }
.preview { background: #f7f9fc; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; }
.hero-preview { min-height: 180px; border-radius: 8px; color: #fff; padding: 16px; display: flex; flex-direction: column; gap: 8px; background: #1e3a5f; white-space: pre-line; }
.hero-preview span, .hero-preview em { font-size: 0.82rem; font-style: normal; opacity: 0.9; }
.composer { display: flex; gap: 10px; align-items: flex-start; padding: 10px; border: 1px solid #e8eef5; border-radius: 10px; background: #fff; }
.composer textarea { flex: 1; }
.news-preview { background: #fff; border-radius: 8px; padding: 10px; }
.news-preview p { white-space: pre-wrap; }
.composer img, .composer video, .news-preview img, .news-preview video { width: min(100%, 320px); border-radius: 8px; }
.file { display: none; }
.side-note { padding: 0 4px 8px; }
.mail { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 640px; }
.contacts { border-right: 1px solid #e5e7eb; background: #f7f9fc; padding: 8px; overflow: auto; }
.contacts-title { margin: 4px 8px 8px; color: #64748b; font-size: 0.82rem; }
.contact { display: flex; gap: 10px; align-items: center; width: 100%; text-align: left; border: 0; background: transparent; border-radius: 8px; padding: 10px 8px; cursor: pointer; font: inherit; }
.contact.on { background: #e8f3ff; }
.avatar { width: 40px; height: 40px; border-radius: 6px; background: #1677ff; color: #fff; display: grid; place-items: center; font-weight: 700; flex: 0 0 auto; }
.who { min-width: 0; }
.who strong, .who em { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.who em { color: #94a3b8; font-style: normal; font-size: 0.78rem; margin-top: 2px; }
.chat { display: flex; flex-direction: column; min-height: 640px; background: #fff; }
.chat header { padding: 14px 16px; border-bottom: 1px solid #eef2f6; font-weight: 700; color: #1e3a5f; }
.chat .log { flex: 1; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.bubble { max-width: min(72%, 520px); background: #f4f6f8; border-radius: 8px; padding: 8px 10px; align-self: flex-start; }
.bubble b { display: block; font-size: 0.75rem; color: #64748b; font-weight: 650; margin-bottom: 2px; }
.bubble.mine { align-self: flex-end; background: #1677ff; color: #fff; }
.bubble.mine b { color: rgba(255, 255, 255, 0.82); }
.chat form, .chat :deep(.composer) { padding: 12px 16px 16px; border-top: 1px solid #eef2f6; }
.chat :deep(.composer) { align-items: stretch; }
.chat textarea { margin: 0; }
.settings { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 16px; padding: 16px; }
.error { color: #dc2626; }
.ok { color: #059669; }
@media (max-width: 900px) {
  .split, .todos, .settings, .mail { grid-template-columns: 1fr; }
}
</style>
