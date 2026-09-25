<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApplicationOut, ReviewRecordOut } from '@/api/types'
import {
  actionLabel,
  actorRoleLabel,
  formatDateTime,
  statusLabel,
  statusTone,
} from '@/utils/statusLabel'

const props = defineProps<{
  application: ApplicationOut | null
  compact?: boolean
  /** 默认展示条数，超出可展开 */
  previewCount?: number
}>()

const expanded = ref(false)
const preview = computed(() => Math.max(3, props.previewCount ?? 4))

const records = computed<ReviewRecordOut[]>(() => {
  const list = props.application?.review_records
  return Array.isArray(list) ? list : []
})

const pipeline = computed(() => {
  const s = props.application?.status || ''
  const rejected = s === 'rejected' || s === 'final_rejected'
  const pastReview = [
    'selected',
    'in_progress',
    'final_submitted',
    'mentor_final_review',
    'committee_final_review',
    'completed',
    'final_rejected',
    'withdrawn',
  ].includes(s)

  type Stage = { key: string; label: string; state: 'done' | 'current' | 'pending' | 'fail' }
  const stages: Stage[] = [
    { key: 'mentor', label: '导师', state: 'pending' },
    { key: 'community', label: '社区', state: 'pending' },
    { key: 'committee', label: '组委会', state: 'pending' },
  ]

  if (pastReview && !rejected) {
    stages.forEach((x) => {
      x.state = 'done'
    })
    return stages
  }

  if (s === 'rejected') {
    const last = [...records.value].reverse().find((r) => (r.to_status || '').includes('reject'))
    const from = last?.from_status || ''
    if (from.includes('committee')) {
      stages[0].state = 'done'
      stages[1].state = 'done'
      stages[2].state = 'fail'
    } else if (from.includes('community')) {
      stages[0].state = 'done'
      stages[1].state = 'fail'
    } else {
      stages[0].state = 'fail'
    }
    return stages
  }

  if (['draft', 'submitted', 'mentor_review'].includes(s)) {
    stages[0].state = 'current'
  } else if (s === 'community_review') {
    stages[0].state = 'done'
    stages[1].state = 'current'
  } else if (s === 'committee_review') {
    stages[0].state = 'done'
    stages[1].state = 'done'
    stages[2].state = 'current'
  }
  return stages
})

const pipelineHint = computed(() => {
  const s = props.application?.status || ''
  if (s === 'community_review') {
    return '名额已预留；还需社区 → 组委会确认后才能启动开发'
  }
  if (s === 'committee_review') {
    return '名额已预留；还需组委会确认后才能启动开发'
  }
  if (s === 'mentor_review' || s === 'submitted') {
    return '第一关：导师审设计文档'
  }
  if (s === 'selected') return '已录取，待启动开发'
  if (s === 'in_progress') return '开发进行中'
  if (s === 'withdrawn') return '已放弃/取消接取'
  return ''
})

const nowExplain = computed(() => {
  const s = props.application?.status || ''
  const map: Record<string, string> = {
    draft: '草稿，尚未提交',
    submitted: '已提交，等待导师审核',
    mentor_review: '导师审设计（第一关）',
    community_review: '社区审核（第二关·名额已预留）',
    committee_review: '组委会审核（第三关·名额已预留）',
    selected: '已录取，待启动开发',
    rejected: '申请未通过',
    withdrawn: '已放弃/取消接取',
    in_progress: '开发中',
    final_submitted: '已提交结项',
    mentor_final_review: '导师结项审核中',
    committee_final_review: '组委会结项审核中',
    final_rejected: '结项未通过',
    completed: '已结项完成',
  }
  return map[s] || statusLabel(s)
})

const hasTimeline = computed(() => records.value.length > 0)
const needsCollapse = computed(() => records.value.length > preview.value)

const visibleRecords = computed(() => {
  if (!needsCollapse.value || expanded.value) return records.value
  return records.value.slice(-preview.value)
})

const hiddenCount = computed(() =>
  needsCollapse.value && !expanded.value
    ? records.value.length - visibleRecords.value.length
    : 0,
)

watch(
  () => props.application?.id,
  () => {
    expanded.value = false
  },
)

function stepKind(r: ReviewRecordOut): 'ok' | 'reject' | 'step' {
  const a = (r.action || '').toLowerCase()
  const to = (r.to_status || '').toLowerCase()
  if (a.includes('reject') || to.includes('reject')) return 'reject'
  if (a.includes('approve') || to === 'selected' || to === 'completed') return 'ok'
  return 'step'
}
</script>

<template>
  <section v-if="application" class="review-progress" :class="{ card: !compact }">
    <h3 v-if="!compact">审核进度</h3>

    <div class="now-row">
      <span class="badge" :class="statusTone(application.status)">{{ statusLabel(application.status) }}</span>
      <strong class="now-text">{{ nowExplain }}</strong>
      <span v-if="pipelineHint" class="hint">{{ pipelineHint }}</span>
    </div>

    <div class="pipe" aria-label="三级审核进度">
      <template v-for="(st, idx) in pipeline" :key="st.key">
        <span class="pipe-step" :class="st.state">{{ st.label }}</span>
        <span v-if="idx < pipeline.length - 1" class="pipe-arrow" aria-hidden="true">→</span>
      </template>
    </div>

    <div v-if="hasTimeline" class="h-scroll-wrap">
      <ol class="h-timeline">
        <li
          v-for="(r, i) in visibleRecords"
          :key="r.id ?? i"
          class="h-step"
          :class="stepKind(r)"
        >
          <span class="h-num">{{ needsCollapse && !expanded ? records.length - visibleRecords.length + i + 1 : i + 1 }}</span>
          <strong class="h-title">{{ actionLabel(r.action) }}</strong>
          <span class="h-meta">
            {{ actorRoleLabel(r.actor_role) || '—' }}
            <template v-if="r.created_at"> · {{ formatDateTime(r.created_at) }}</template>
          </span>
          <p v-if="r.comment" class="h-note">{{ r.comment }}</p>
        </li>
      </ol>
    </div>
    <p v-else class="muted empty">暂无审核流水</p>

    <button
      v-if="hiddenCount > 0"
      type="button"
      class="more-btn"
      @click="expanded = true"
    >
      展开更早 {{ hiddenCount }} 步
    </button>
    <button
      v-else-if="needsCollapse && expanded"
      type="button"
      class="more-btn"
      @click="expanded = false"
    >
      收起
    </button>
  </section>
</template>

<style scoped>
.now-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.55rem;
  align-items: center;
  margin: 0 0 0.55rem;
}
.now-text {
  font-size: 0.9rem;
  color: #1e3a5f;
}
.hint {
  font-size: 0.78rem;
  color: #64748b;
  width: 100%;
}
.pipe {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
  margin: 0 0 0.65rem;
}
.pipe-step {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  background: #f1f5f9;
  color: #94a3b8;
}
.pipe-step.done {
  background: #dcfce7;
  color: #166534;
}
.pipe-step.current {
  background: #dbeafe;
  color: #1d4ed8;
}
.pipe-step.fail {
  background: #fee2e2;
  color: #b91c1c;
}
.pipe-arrow {
  color: #cbd5e1;
  font-size: 0.72rem;
}
.h-scroll-wrap {
  overflow-x: auto;
  padding-bottom: 0.25rem;
  margin: 0 -0.15rem;
}
.h-timeline {
  list-style: none;
  margin: 0;
  padding: 0.15rem 0.15rem 0.35rem;
  display: flex;
  gap: 0.55rem;
  min-width: min-content;
}
.h-step {
  flex: 0 0 auto;
  width: 11rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  position: relative;
}
.h-step::after {
  content: '';
  position: absolute;
  right: -0.4rem;
  top: 50%;
  width: 0.4rem;
  height: 2px;
  background: #e2e8f0;
}
.h-step:last-child::after {
  display: none;
}
.h-step.ok {
  border-color: #86efac;
  background: #f0fdf4;
}
.h-step.reject {
  border-color: #fca5a5;
  background: #fef2f2;
}
.h-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  height: 1.15rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  background: #e2e8f0;
  color: #475569;
  margin-bottom: 0.25rem;
}
.h-step.ok .h-num {
  background: #bbf7d0;
  color: #166534;
}
.h-step.reject .h-num {
  background: #fecaca;
  color: #b91c1c;
}
.h-title {
  display: block;
  font-size: 0.82rem;
  color: #0f172a;
  margin-bottom: 0.15rem;
  line-height: 1.3;
}
.h-meta {
  display: block;
  font-size: 0.7rem;
  color: #94a3b8;
  line-height: 1.35;
}
.h-note {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: #475569;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.more-btn {
  margin-top: 0.45rem;
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}
.empty {
  margin: 0;
  font-size: 0.85rem;
}
</style>
