<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type DocKey = 'faq' | 'org' | 'student' | 'mentor' | 'flow'

const route = useRoute()
const router = useRouter()

const activeDoc = ref<DocKey | null>(null)
const activeId = ref('')
const showTop = ref(false)
const helpTrack = ref<HTMLElement | null>(null)
const historyPaused = ref(false)
const historyReverse = ref(false)
const detailRef = ref<HTMLElement | null>(null)

const helpDocs: {
  key: DocKey
  title: string
  desc: string
  icon: string
  tone: string
}[] = [
  { key: 'faq', title: '热点问题', desc: '报名、审核、结项常见疑问与排障说明', icon: '🔥', tone: 'hot' },
  { key: 'org', title: '组织指南', desc: '社区报名、字段配置、二级审核与公示', icon: '🪐', tone: 'org' },
  { key: 'student', title: '学生指南', desc: '注册申请、三级审核跟踪到结项全流程', icon: '🎓', tone: 'stu' },
  { key: 'mentor', title: '导师指南', desc: '出题发布、一审指导与结项初审要点', icon: '📋', tone: 'mentor' },
  { key: 'flow', title: '经典流程指南', desc: '对标 OSPP 经典模式的完整活动链路', icon: '📝', tone: 'flow' },
]

const docMeta: Record<
  DocKey,
  { title: string; toc: { id: string; label: string; sub?: boolean }[] }
> = {
  faq: {
    title: '热点问题',
    toc: [
      { id: 'faq-q1', label: '已是组织成员能否申请？' },
      { id: 'faq-q2', label: '能否申请多个项目？' },
      { id: 'faq-q3', label: '审核被驳回怎么办？' },
      { id: 'faq-q4', label: '结项是否必须 PR/MR？' },
      { id: 'faq-q5', label: '缺少 Idempotency-Key？' },
      { id: 'faq-q6', label: '是否发证书/报酬？' },
    ],
  },
  org: {
    title: '组织指南',
    toc: [
      { id: 'org-1', label: '1. 组织登录' },
      { id: 'org-2', label: '2. 社区报名与准入' },
      { id: 'org-3', label: '3. 配置专属字段' },
      { id: 'org-4', label: '4. 社区二级审核' },
      { id: 'org-5', label: '5. 组委会终审与公示' },
    ],
  },
  student: {
    title: '学生指南',
    toc: [
      { id: 'stu-1', label: '1. 注册与登录' },
      { id: 'stu-2', label: '2. 浏览并选择项目' },
      { id: 'stu-3', label: '3. 提交申请书' },
      { id: 'stu-4', label: '4. 跟踪三级审核' },
      { id: 'stu-5', label: '5. 中选、开发与结项' },
    ],
  },
  mentor: {
    title: '导师指南',
    toc: [
      { id: 'men-1', label: '1. 进入导师工作台' },
      { id: 'men-2', label: '2. 发布项目' },
      { id: 'men-3', label: '3. 申请一审' },
      { id: 'men-4', label: '4. 过程指导' },
      { id: 'men-5', label: '5. 结项初审' },
    ],
  },
  flow: {
    title: '经典流程指南',
    toc: [
      { id: 'flow-intro', label: '活动简介' },
      { id: 'flow-roles', label: '角色与权限' },
      { id: 'flow-1', label: '1. 组织报名与审核', sub: true },
      { id: 'flow-2', label: '2. 组织发布项目', sub: true },
      { id: 'flow-3', label: '3. 学生申请及审核', sub: true },
      { id: 'flow-4', label: '4. 中选', sub: true },
      { id: 'flow-5', label: '5. 开发与成果提交', sub: true },
      { id: 'flow-6', label: '6. 过程沟通', sub: true },
      { id: 'flow-7', label: '7. 结项考核', sub: true },
      { id: 'flow-8', label: '8. 结项公示', sub: true },
    ],
  },
}

const historyYears = [
  { year: '2025', note: '开源之夏', tone: 0 },
  { year: '2024', note: '开源之夏', tone: 1 },
  { year: '2023', note: '开源之夏', tone: 2 },
  { year: '2022', note: '开源之夏', tone: 0 },
  { year: '2021', note: '开源之夏', tone: 1 },
  { year: '2020', note: '开源之夏', tone: 2 },
]
const historyLoop = [...historyYears, ...historyYears]

const currentToc = computed(() => (activeDoc.value ? docMeta[activeDoc.value].toc : []))
const currentTitle = computed(() => (activeDoc.value ? docMeta[activeDoc.value].title : ''))

function scrollRail(el: HTMLElement | null, dir: 1 | -1) {
  if (!el) return
  el.scrollBy({ left: dir * 280, behavior: 'smooth' })
}

function nudgeHistory(dir: 1 | -1) {
  historyReverse.value = dir < 0
  window.setTimeout(() => {
    historyReverse.value = false
  }, 2500)
}

async function openDoc(key: DocKey) {
  activeDoc.value = key
  activeId.value = docMeta[key].toc[0]?.id || ''
  await router.replace({ hash: `#doc-${key}` })
  await nextTick()
  detailRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function closeDoc() {
  activeDoc.value = null
  activeId.value = ''
  await router.replace({ hash: '' })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function scrollTo(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  activeId.value = id
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function onScroll() {
  showTop.value = window.scrollY > 420
  if (!activeDoc.value) return
  const offset = 120
  let current = currentToc.value[0]?.id || ''
  for (const item of currentToc.value) {
    const el = document.getElementById(item.id)
    if (!el) continue
    if (el.getBoundingClientRect().top <= offset) current = item.id
  }
  activeId.value = current
}

function toTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function sharePage() {
  const url = window.location.href
  try {
    if (navigator.share) {
      await navigator.share({ title: '参与指南', url })
      return
    }
  } catch {
    /* ignore */
  }
  try {
    await navigator.clipboard.writeText(url)
    window.alert('链接已复制到剪贴板')
  } catch {
    window.prompt('复制参与指南链接：', url)
  }
}

const hashToDoc: Record<string, DocKey> = {
  'doc-faq': 'faq',
  'doc-org': 'org',
  'doc-student': 'student',
  'doc-mentor': 'mentor',
  'doc-flow': 'flow',
  'sec-faq': 'faq',
  'sec-org-ops': 'org',
  'sec-student': 'student',
  'sec-mentor': 'mentor',
  'sec-flow': 'flow',
}

onMounted(async () => {
  window.addEventListener('scroll', onScroll, { passive: true })
  await nextTick()
  const hash = route.hash.replace('#', '')
  const mapped = hashToDoc[hash]
  if (mapped) await openDoc(mapped)
  onScroll()
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <div class="guide-page">
    <section class="guide-banner">
      <div class="guide-banner-shapes" aria-hidden="true">
        <span class="shape s1">☺</span>
        <span class="shape s2">◕</span>
        <span class="shape s3">△</span>
        <span class="blob b1" />
        <span class="blob b2" />
        <span class="blob b3" />
      </div>
      <div class="guide-banner-inner">
        <h1>参与指南</h1>
        <p>参与者可以根据自己的角色及问题通过参与指南查看相应解决方案</p>
      </div>
    </section>

    <section class="guide-help-section">
      <h2>帮助文档</h2>
      <p class="help-hint">请先选择下方卡片，再查看对应详细说明</p>
      <div class="help-grid-wrap">
        <button class="h-scroll-btn help-nav-btn" type="button" aria-label="向左" @click="scrollRail(helpTrack, -1)">‹</button>
        <div ref="helpTrack" class="help-rail">
          <button
            v-for="d in helpDocs"
            :key="d.key"
            type="button"
            class="help-card"
            :class="[d.tone, { selected: activeDoc === d.key }]"
            @click="openDoc(d.key)"
          >
            <span class="help-icon">{{ d.icon }}</span>
            <strong>{{ d.title }}</strong>
            <span>{{ d.desc }}</span>
            <em class="help-cta">点击查看详情 →</em>
          </button>
        </div>
        <button class="h-scroll-btn help-nav-btn" type="button" aria-label="向右" @click="scrollRail(helpTrack, 1)">›</button>
      </div>
    </section>

    <!-- 仅点击卡片后展开详情 -->
    <div v-if="activeDoc" ref="detailRef" class="guide-detail-wrap">
      <div class="guide-detail-bar">
        <h2>{{ currentTitle }}</h2>
        <button class="btn secondary sm" type="button" @click="closeDoc">返回帮助文档</button>
      </div>

      <div class="guide-layout">
        <article class="guide-main">
          <!-- 热点问题 -->
          <template v-if="activeDoc === 'faq'">
            <section id="faq-q1" class="guide-sec">
              <h3>学生已经是组织的一员，可以申请该组织的项目吗？</h3>
              <div class="guide-tags">
                <span class="guide-tag">身份独立</span>
                <span class="guide-tag teal">可申请</span>
              </div>
              <p>
                可以。本平台的<strong>项目申请</strong>与俱乐部<strong>成员身份</strong>相互独立：即便你已通过官网 / 飞书完成入会（PR + 信息表），
                仍需在本平台单独提交项目申请书，才会进入导师 → 社区 → 组委会的审核链路。
              </p>
              <div class="guide-callout ok">
                <span class="ico">✅</span>
                <div class="body">
                  <strong>小结</strong>
                  <p>入会 ≠ 中选。加入俱乐部不替代申请，也不自动占用项目名额。</p>
                </div>
              </div>
            </section>
            <section id="faq-q2" class="guide-sec">
              <h3>一个学生可以同时申请多个项目吗？</h3>
              <div class="guide-tags">
                <span class="guide-tag orange">多项目</span>
                <span class="guide-tag">同项目唯一</span>
              </div>
              <p>
                可以同时申请多个不同项目。但对<strong>同一项目</strong>，系统默认仅保留一条有效申请，避免重复占用审核队列。
                请按兴趣与时间成本合理筛选，优先提交准备充分的申请书。
              </p>
              <ul class="guide-checklist">
                <li>不同项目：可并行申请，状态各自独立跟踪</li>
                <li>同一项目：默认一条申请；如需重提请联系组委会</li>
                <li>中选后请集中精力完成该项目，避免同时占用过多名额</li>
              </ul>
            </section>
            <section id="faq-q3" class="guide-sec">
              <h3>审核被驳回后怎么办？</h3>
              <p>驳回不是终点。请先在「我的申请」阅读审核意见，再按意见补充材料或调整方案。</p>
              <ol class="guide-steps">
                <li>
                  <span class="n">1</span>
                  <div class="t">
                    <b>阅读意见</b>
                    <span>导师 / 社区 / 组委会驳回时都会留下可追溯意见（写入审核流水）。</span>
                  </div>
                </li>
                <li>
                  <span class="n">2</span>
                  <div class="t">
                    <b>按意见修订</b>
                    <span>补齐申请正文、附加字段、仓库信息等；必要时通过留言与导师沟通。</span>
                  </div>
                </li>
                <li>
                  <span class="n">3</span>
                  <div class="t">
                    <b>同项目重提</b>
                    <span>受「同项目唯一申请」约束时，请联系组委会协助处理后再提交。</span>
                  </div>
                </li>
              </ol>
            </section>
            <section id="faq-q4" class="guide-sec">
              <h3>结项必须提交 PR/MR 吗？</h3>
              <div class="guide-tags">
                <span class="guide-tag violet">PR / MR</span>
                <span class="guide-tag">结项报告</span>
              </div>
              <p>
                是。结项材料以<strong>可核验的 PR/MR 链接</strong> + <strong>结项报告</strong>为主；报告可使用飞书 / 文档外链。
                部分社区还会要求额外字段（如 patch、镜像运维说明等），以该社区配置为准。
              </p>
              <div class="guide-callout">
                <span class="ico">📎</span>
                <div class="body">
                  <strong>核验提示</strong>
                  <p>提交前请确认仓库可访问、PR 状态清晰，且 git email 与平台资料邮箱一致。</p>
                </div>
              </div>
            </section>
            <section id="faq-q5" class="guide-sec">
              <h3>为什么提示缺少 Idempotency-Key？</h3>
              <p>
                本平台写操作启用企业级<strong>幂等流水</strong>：同一关键动作（审核、结项提交等）需携带
                <code>X-Idempotency-Key</code>，防止网络重试导致重复记账。
              </p>
              <div class="guide-callout warn">
                <span class="ico">⚠️</span>
                <div class="body">
                  <strong>给 API 调试者</strong>
                  <p>网页端会自动携带该头；用 Postman / curl 时请自行生成唯一 Key（UUID 即可）。</p>
                </div>
              </div>
            </section>
            <section id="faq-q6" class="guide-sec">
              <h3>本平台发证书 / 发钱吗？</h3>
              <p>
                本平台<strong>不含</strong> OSPP 官方劳务报酬与证书体系，定位为华科开放原子开源俱乐部实习运营与流程演练。
                俱乐部内部福利、荣誉证明等，按俱乐部当期政策另行安排，不在本系统结算。
              </p>
              <div class="guide-callout">
                <span class="ico">ℹ️</span>
                <div class="body">
                  <strong>和 OSPP 的差异</strong>
                  <p>弱化协议签署与报酬；强化分社区字段、三级审核与企业级三表流水追溯。</p>
                </div>
              </div>
            </section>
          </template>

          <!-- 组织指南 -->
          <template v-else-if="activeDoc === 'org'">
            <section id="org-1" class="guide-sec">
              <h3>1. 组织登录</h3>
              <div class="guide-tags">
                <span class="guide-tag">导师</span>
                <span class="guide-tag teal">社区管理员</span>
                <span class="guide-tag violet">组委会</span>
              </div>
              <p>
                使用右上角「组织登录」进入组织侧。同一账号体系，按角色进入对应工作台：导师管项目与一审，
                社区管理员管报名 / 字段 / 二审，组委会管准入、终审与公示。
              </p>
              <div class="guide-callout">
                <span class="ico">🔑</span>
                <div class="body">
                  <strong>演示账号</strong>
                  <p>可用 *@demo.hust.edu.cn / Demo@123456 体验不同角色工作台（以种子数据为准）。</p>
                </div>
              </div>
            </section>
            <section id="org-2" class="guide-sec">
              <h3>2. 社区报名与准入</h3>
              <p>社区管理员提交报名资料后，由组委会审核。未通过准入的社区<strong>不能发布项目</strong>。</p>
              <ul class="guide-checklist">
                <li>填写社区简介、主页、联系人与对外仓库（Gitea / 镜像）外链</li>
                <li>提交后状态为 pending，等待组委会审核</li>
                <li>通过后变为 approved，方可创建并上线项目</li>
                <li>驳回时请按意见修订后再次提交</li>
              </ul>
            </section>
            <section id="org-3" class="guide-sec">
              <h3>3. 配置专属字段</h3>
              <p>
                可为社区配置申请 / 结项附加字段（JSON Schema），让不同技术栈社区收集差异化材料，例如：
              </p>
              <div class="guide-role-grid">
                <div class="guide-role">
                  <div class="emoji">🧩</div>
                  <strong>内核 / 系统类</strong>
                  <p>要求 patch 链接、架构说明、回归测试结果等。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">🪞</div>
                  <strong>镜像 / 运维类</strong>
                  <p>要求运维经验、监控方案、故障演练记录等。</p>
                </div>
              </div>
              <div class="guide-callout ok">
                <span class="ico">💡</span>
                <div class="body">
                  <strong>建议</strong>
                  <p>字段宜少而精：只收审核必需信息，避免学生填写负担过重。</p>
                </div>
              </div>
            </section>
            <section id="org-4" class="guide-sec">
              <h3>4. 社区二级审核</h3>
              <p>
                导师一审通过后，社区管理员对本社区申请进行二审：通过则进入组委会终审；驳回须写明原因。
                每次结论都会写入企业级三表流水（review / audit / workflow），可追溯、可幂等。
              </p>
              <ol class="guide-steps">
                <li>
                  <span class="n">1</span>
                  <div class="t"><b>核对材料完整性</b><span>申请书、附加字段、仓库与身份信息是否齐全。</span></div>
                </li>
                <li>
                  <span class="n">2</span>
                  <div class="t"><b>评估社区匹配度</b><span>技术栈、难度、名额与学生背景是否匹配。</span></div>
                </li>
                <li>
                  <span class="n">3</span>
                  <div class="t"><b>给出可执行意见</b><span>驳回时写清「缺什么 / 怎么改」，方便学生修订。</span></div>
                </li>
              </ol>
            </section>
            <section id="org-5" class="guide-sec">
              <h3>5. 组委会终审与公示</h3>
              <p>
                组委会完成终审后发布<strong>中选公示</strong>；结项阶段再发布<strong>结项公示</strong>，完成活动闭环。
                公示结果对学生与社区可见，作为后续开发与验收依据。
              </p>
              <div class="guide-callout warn">
                <span class="ico">📢</span>
                <div class="body">
                  <strong>注意</strong>
                  <p>本平台以公示替代 OSPP 协议签署环节；请关注公示时间窗口与异议反馈渠道。</p>
                </div>
              </div>
            </section>
          </template>

          <!-- 学生指南 -->
          <template v-else-if="activeDoc === 'student'">
            <section id="stu-1" class="guide-sec">
              <h3>1. 注册与登录</h3>
              <div class="guide-tags">
                <span class="guide-tag">学生登录</span>
                <span class="guide-tag teal">资料完善</span>
              </div>
              <p>
                使用右上角「学生登录」或先完成注册。建议尽早完善 GitHub / Gitea ID、常用邮箱，
                便于审核与结项时身份核验。
              </p>
              <ul class="guide-checklist">
                <li>使用学校邮箱或常用邮箱注册，保证能收到通知</li>
                <li>完善个人简介与技术栈标签，提升申请可信度</li>
                <li>绑定可访问的代码托管账号，方便提交 PR/MR</li>
              </ul>
            </section>
            <section id="stu-2" class="guide-sec">
              <h3>2. 浏览并选择项目</h3>
              <p>
                在「查看项目」阅读课题描述、技术栈、难度、名额与仓库地址。优先选择与自身基础匹配、
                时间可完成的课题，进入详情页后再动手写申请。
              </p>
              <div class="guide-callout">
                <span class="ico">🎯</span>
                <div class="body">
                  <strong>选题建议</strong>
                  <p>先看仓库 README 与 issue，确认环境可搭建、任务边界清晰，再投入申请书撰写。</p>
                </div>
              </div>
            </section>
            <section id="stu-3" class="guide-sec">
              <h3>3. 提交申请书</h3>
              <p>申请书建议包含：背景理解、实施方案、里程碑、风险与时间表。按社区要求补充附加字段。</p>
              <ol class="guide-steps">
                <li>
                  <span class="n">1</span>
                  <div class="t"><b>写清「做什么」</b><span>目标、范围、验收标准，避免空泛口号。</span></div>
                </li>
                <li>
                  <span class="n">2</span>
                  <div class="t"><b>写清「怎么做」</b><span>技术路线、关键模块、参考资料与验证方式。</span></div>
                </li>
                <li>
                  <span class="n">3</span>
                  <div class="t"><b>补齐专属字段</b><span>如 patch 链接、镜像经验等，漏填容易被驳回。</span></div>
                </li>
              </ol>
            </section>
            <section id="stu-4" class="guide-sec">
              <h3>4. 跟踪三级审核</h3>
              <p>审核顺序固定为：<strong>导师 → 社区 → 组委会</strong>。在「我的申请」查看状态、意见，并可留言沟通。</p>
              <div class="guide-role-grid">
                <div class="guide-role">
                  <div class="emoji">👨‍🏫</div>
                  <strong>导师一审</strong>
                  <p>评估方案可行性与个人匹配度，给出通过 / 驳回。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">🏛️</div>
                  <strong>社区二审</strong>
                  <p>从社区资源与课题匹配度复核，确认名额安排。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">⚖️</div>
                  <strong>组委会终审</strong>
                  <p>统一规则终审，通过后进入中选公示。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">💬</div>
                  <strong>留言沟通</strong>
                  <p>关键结论仍以审核流水为准，留言用于澄清细节。</p>
                </div>
              </div>
            </section>
            <section id="stu-5" class="guide-sec">
              <h3>5. 中选、开发与结项</h3>
              <p>
                中选公示后进入开发期：在外部仓库按里程碑推进，按时提交 PR/MR 与结项报告，
                等待导师结项初审与组委会成果审核，并关注结项公示。
              </p>
              <div class="guide-callout warn">
                <span class="ico">📌</span>
                <div class="body">
                  <strong>硬性提示</strong>
                  <p class="guide-hl" style="margin-top: 0.35rem">git email 须与平台资料邮箱一致，否则结项核验可能失败。</p>
                </div>
              </div>
            </section>
          </template>

          <!-- 导师指南 -->
          <template v-else-if="activeDoc === 'mentor'">
            <section id="men-1" class="guide-sec">
              <h3>1. 进入导师工作台</h3>
              <div class="guide-tags">
                <span class="guide-tag">组织登录</span>
                <span class="guide-tag orange">导师台</span>
              </div>
              <p>
                右上角「组织登录」后进入「导师台」，可管理本人项目、待审申请与结项初审队列。
                请确认账号已绑定到对应社区，否则无法发布归属该社区的项目。
              </p>
            </section>
            <section id="men-2" class="guide-sec">
              <h3>2. 发布项目</h3>
              <p>创建项目时请完整填写下列信息，社区准入通过后方可对学生可见并接受申请。</p>
              <ul class="guide-checklist">
                <li>标题、描述、难度与技术栈标签</li>
                <li>名额、仓库链接与参考资料</li>
                <li>归属已 approved 的社区</li>
                <li>验收标准与建议里程碑（便于学生写申请）</li>
              </ul>
              <div class="guide-callout">
                <span class="ico">✍️</span>
                <div class="body">
                  <strong>出题建议</strong>
                  <p>任务边界清晰、可在暑期周期内完成；避免过大「研究型」题目导致结项困难。</p>
                </div>
              </div>
            </section>
            <section id="men-3" class="guide-sec">
              <h3>3. 申请一审</h3>
              <p>对学生申请进行导师级审核：通过则进入社区审核；驳回须写明可执行原因。</p>
              <ol class="guide-steps">
                <li>
                  <span class="n">1</span>
                  <div class="t"><b>看方案</b><span>是否理解课题、路线是否可行、时间是否现实。</span></div>
                </li>
                <li>
                  <span class="n">2</span>
                  <div class="t"><b>看背景</b><span>技术栈与过往贡献是否匹配项目难度。</span></div>
                </li>
                <li>
                  <span class="n">3</span>
                  <div class="t"><b>写意见</b><span>通过 / 驳回均写入流水；驳回请指出具体修改点。</span></div>
                </li>
              </ol>
            </section>
            <section id="men-4" class="guide-sec">
              <h3>4. 过程指导</h3>
              <p>
                中选后通过申请留言与学生保持沟通：对齐里程碑、代码规范与合并节奏。
                过程讨论可灵活进行，但<strong>关键结论仍以审核流水为准</strong>。
              </p>
              <div class="guide-callout ok">
                <span class="ico">🤝</span>
                <div class="body">
                  <strong>沟通建议</strong>
                  <p>约定周报或 Issue 节奏；重大范围变更请留痕，避免结项时验收口径不一致。</p>
                </div>
              </div>
            </section>
            <section id="men-5" class="guide-sec">
              <h3>5. 结项初审</h3>
              <p>核验 PR/MR 是否达标、报告是否完整、附加字段是否齐全；通过后进入组委会成果审核。</p>
              <ul class="guide-checklist">
                <li>PR/MR 可访问，变更与课题目标对应</li>
                <li>结项报告结构完整（目标 / 工作 / 结果 / 反思）</li>
                <li>社区专属字段已填写且可核验</li>
                <li>学生身份与 git email 一致</li>
              </ul>
            </section>
          </template>

          <!-- 经典流程 -->
          <template v-else-if="activeDoc === 'flow'">
            <section id="flow-intro" class="guide-sec">
              <h2>📘 活动简介</h2>
              <div class="guide-tags">
                <span class="guide-tag">对标 OSPP</span>
                <span class="guide-tag teal">华科开放原子</span>
                <span class="guide-tag orange">经典模式</span>
              </div>
              <p>
                开源之夏面向高校学生组织开源贡献：申请 → 中选 → 开发 → 结项。
                本平台复刻其核心闭环，用于<strong>华中科技大学开放原子开源俱乐部</strong>实习运营与流程演练。
              </p>
              <ul class="guide-checklist">
                <li>组织（社区）报名与审核</li>
                <li>组织发布项目</li>
                <li>学生项目申请与多级审核</li>
                <li>中选公示 → 项目开发 → 结项审核与公示</li>
              </ul>
              <div class="guide-callout">
                <span class="ico">🧭</span>
                <div class="body">
                  <strong>本地化差异</strong>
                  <p>
                    弱化协议签署、劳务报酬与官方证书；增强分社区专属字段与企业级审核流水。
                    正文结构前期对标 OSPP 帮助文档，后续将按俱乐部实际运营修订。
                  </p>
                </div>
              </div>
            </section>
            <section id="flow-roles" class="guide-sec">
              <h2>👥 角色与权限</h2>
              <div class="guide-role-grid">
                <div class="guide-role">
                  <div class="emoji">🎓</div>
                  <strong>学生</strong>
                  <p>浏览项目、提交申请、留言沟通、开发与结项提交。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">📋</div>
                  <strong>导师</strong>
                  <p>发布项目、申请一审、过程指导、结项初审。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">🪐</div>
                  <strong>社区管理员</strong>
                  <p>社区报名、专属字段配置、申请二级审核。</p>
                </div>
                <div class="guide-role">
                  <div class="emoji">⚖️</div>
                  <strong>组委会</strong>
                  <p>社区准入、终审、中选 / 结项公示与全局规则。</p>
                </div>
              </div>
            </section>
            <section id="flow-1" class="guide-sec">
              <h3>1. 组织报名与审核</h3>
              <p>社区提交资料；组委会审核状态机：<code>pending → approved / rejected</code>。仅 approved 社区可发项目。</p>
            </section>
            <section id="flow-2" class="guide-sec">
              <h3>2. 组织发布项目</h3>
              <p>导师创建并上线项目，填写仓库、名额、技术栈与验收说明，对学生可见并开放申请。</p>
            </section>
            <section id="flow-3" class="guide-sec">
              <h3>3. 学生项目申请及审核</h3>
              <p>
                学生提交申请书与附加字段；审核顺序<strong>导师 → 社区 → 组委会</strong>。
                每次动作写入状态机 + 三表流水，支持幂等与乐观锁版本控制。
              </p>
            </section>
            <section id="flow-4" class="guide-sec">
              <h3>4. 中选</h3>
              <p>终审通过后中选；以<strong>中选公示</strong>替代 OSPP 协议环节，公示后可推进到「开发中」。</p>
            </section>
            <section id="flow-5" class="guide-sec">
              <h3>5. 项目开发与成果提交</h3>
              <p>在外部仓库开发；结项提交 PR/MR、结项报告，以及社区配置的附加字段材料。</p>
            </section>
            <section id="flow-6" class="guide-sec">
              <h3>6. 过程沟通与记录</h3>
              <p>申请留言用于日常沟通；review_records / audit_logs / workflow_events 保证关键节点全程可追溯。</p>
            </section>
            <section id="flow-7" class="guide-sec">
              <h3>7. 结项考核</h3>
              <p>导师结项初审 → 组委会成果审核。任一级驳回需按意见修订后再次提交。</p>
            </section>
            <section id="flow-8" class="guide-sec">
              <h3>8. 结项公示</h3>
              <p>组委会发布结项公示；本平台不做报酬接收与证书发放，福利按俱乐部政策另行安排。</p>
              <div class="guide-callout ok">
                <span class="ico">🏁</span>
                <div class="body">
                  <strong>闭环完成</strong>
                  <p>从社区准入到结项公示，完整覆盖经典模式全链路，可在本平台演练与落地。</p>
                </div>
              </div>
            </section>
          </template>
        </article>

        <aside class="guide-toc" aria-label="目录">
          <div class="guide-toc-card">
            <div class="guide-toc-title">目录</div>
            <nav class="guide-toc-list">
              <button
                v-for="item in currentToc"
                :key="item.id"
                type="button"
                class="guide-toc-item"
                :class="{ active: activeId === item.id, sub: item.sub }"
                @click="scrollTo(item.id)"
              >
                {{ item.label }}
              </button>
            </nav>
          </div>
        </aside>
      </div>
    </div>

    <section class="history-section">
      <h2>往届回顾</h2>
      <p class="history-sub">开源之夏历年活动回顾（展示用，链接指向 OSPP 官网）</p>
      <div class="history-wrap">
        <button class="h-scroll-btn light history-arrow" type="button" aria-label="短暂向右" @click="nudgeHistory(-1)">‹</button>
        <div
          class="history-marquee"
          :class="{ paused: historyPaused, reverse: historyReverse }"
          @mouseenter="historyPaused = true"
          @mouseleave="historyPaused = false"
        >
          <div class="history-marquee-track">
            <a
              v-for="(h, i) in historyLoop"
              :key="`${h.year}-${i}`"
              class="history-card"
              :class="`tone-${h.tone}`"
              href="https://summer.ospp.ac.cn/"
              target="_blank"
              rel="noopener"
            >
              <div class="history-art" />
              <div class="history-bar">{{ h.note }} {{ h.year }}</div>
            </a>
          </div>
        </div>
        <button class="h-scroll-btn light history-arrow" type="button" aria-label="继续向左" @click="nudgeHistory(1)">›</button>
      </div>
    </section>

    <div class="fab-stack">
      <button class="fab" type="button" title="分享" @click="sharePage">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="18" cy="5" r="2.2" />
          <circle cx="6" cy="12" r="2.2" />
          <circle cx="18" cy="19" r="2.2" />
          <path d="M8 11l8-5M8 13l8 5" />
        </svg>
      </button>
      <button v-show="showTop" class="fab" type="button" title="回到顶部" @click="toTop">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 14l6-6 6 6" />
          <path d="M6 6h12" />
        </svg>
      </button>
    </div>
  </div>
</template>
