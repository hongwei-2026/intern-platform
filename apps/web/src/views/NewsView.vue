<script setup lang="ts">
const items = [
  {
    date: '2026-03',
    title: '开源实习管理系统进入任务3联调',
    body: '完成 JWT 鉴权、社区/项目/三级审核与企业级流水，前端按华科官网风格改版。',
  },
  {
    date: '2026-03',
    title: '实习全流程上线',
    body: '社区报名 → 项目发布 → 学生申请 → 三级审核 → 中选公示 → 结项审核，支持分社区申请字段。',
  },
  {
    date: '持续更新',
    title: '俱乐部动态请见官网',
    body: '新闻、百科、翻译团队与镜像站服务以俱乐部门户为准。',
    href: 'https://hust.openatom.club/',
  },
]
</script>

<template>
  <div class="page">
    <h1 class="page-title">最新动态</h1>
    <p class="page-desc">实习平台与俱乐部相关进展。更完整新闻请访问华科开放原子开源俱乐部官网。</p>

    <div class="stack">
      <article v-for="n in items" :key="n.title" class="card">
        <p class="muted" style="margin: 0 0 0.35rem">{{ n.date }}</p>
        <h3>{{ n.title }}</h3>
        <p class="muted">{{ n.body }}</p>
        <p v-if="n.href" style="margin-top: 0.75rem">
          <a :href="n.href" target="_blank" rel="noopener">前往俱乐部官网 →</a>
        </p>
      </article>
    </div>
  </div>
</template>
