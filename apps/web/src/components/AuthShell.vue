<script setup lang="ts">
import { RouterLink } from 'vue-router'

withDefaults(
  defineProps<{
    variant?: 'student' | 'mentor' | 'org' | 'committee'
    kicker?: string
    title: string
    lead?: string
    points?: string[]
    homeTo?: string
    showHome?: boolean
  }>(),
  {
    variant: 'student',
    kicker: '华科开源原子',
    lead: '',
    points: () => [],
    homeTo: '/',
    showHome: true,
  },
)
</script>

<template>
  <div class="auth-page" :class="`is-${variant}`">
    <div class="auth-backdrop" aria-hidden="true">
      <div class="bg-grid" />
      <div class="bg-mesh" />
      <div class="bg-orb orb-a" />
      <div class="bg-orb orb-b" />
      <div class="bg-orb orb-c" />
      <div class="bg-ring ring-a" />
      <div class="bg-ring ring-b" />
      <svg class="bg-nodes" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice">
        <g class="node-lines">
          <path d="M80 120 L220 80 L360 160 L520 90 L680 150" />
          <path d="M40 320 L180 280 L300 360 L480 300 L720 380" />
          <path d="M120 480 L260 420 L420 500 L600 440 L760 520" />
          <path d="M220 80 L180 280 L260 420" />
          <path d="M520 90 L480 300 L600 440" />
        </g>
        <g class="node-dots">
          <circle cx="80" cy="120" r="3.5" />
          <circle cx="220" cy="80" r="2.5" />
          <circle cx="360" cy="160" r="3" />
          <circle cx="520" cy="90" r="2.5" />
          <circle cx="680" cy="150" r="3.5" />
          <circle cx="180" cy="280" r="3" />
          <circle cx="480" cy="300" r="2.5" />
          <circle cx="260" cy="420" r="3" />
          <circle cx="600" cy="440" r="2.5" />
          <circle cx="720" cy="380" r="3" />
        </g>
      </svg>
    </div>

    <RouterLink v-if="showHome" class="auth-home" :to="homeTo">← 返回首页</RouterLink>
    <div class="auth-shell">
      <aside class="auth-brand">
        <div class="brand-pattern" aria-hidden="true" />
        <div class="brand-glow" />
        <div class="brand-inner">
          <img class="brand-mark" src="/logos/penguin-blue.svg" alt="" />
          <p class="brand-kicker">{{ kicker }}</p>
          <h1>{{ title }}</h1>
          <p v-if="lead" class="brand-lead">{{ lead }}</p>
          <ul v-if="points.length" class="brand-points">
            <li v-for="item in points" :key="item">{{ item }}</li>
          </ul>
        </div>
      </aside>

      <section class="auth-main">
        <header v-if="$slots.head" class="auth-head">
          <slot name="head" />
        </header>
        <div class="auth-body">
          <slot />
        </div>
        <footer v-if="$slots.foot" class="auth-foot">
          <slot name="foot" />
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  --auth-ink: #0f2744;
  --auth-accent: #1d4ed8;
  --auth-accent-soft: #dbeafe;
  --auth-brand-from: #12365f;
  --auth-brand-mid: #1e4d8c;
  --auth-brand-to: #2563eb;
  --auth-orb-a: rgba(37, 99, 235, 0.28);
  --auth-orb-b: rgba(14, 165, 233, 0.2);
  --auth-orb-c: rgba(59, 130, 246, 0.16);
  --auth-grid: rgba(37, 99, 235, 0.07);
  --auth-node: rgba(29, 78, 216, 0.22);
  --auth-display: 'Noto Serif SC', 'Songti SC', serif;
  --auth-sans: 'IBM Plex Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;

  position: relative;
  isolation: isolate;
  min-height: 100vh;
  margin: 0 calc(50% - 50vw);
  padding: 1.25rem clamp(1rem, 3vw, 2rem) 3rem;
  overflow: hidden;
  background: linear-gradient(165deg, #e8f0fb 0%, #f4f7fb 42%, #eef4fa 72%, #f8fafc 100%);
  font-family: var(--auth-sans);
  animation: page-in 0.45s ease both;
}

.auth-page.is-mentor {
  --auth-accent: #ea580c;
  --auth-accent-soft: #ffedd5;
  --auth-brand-from: #7c2d12;
  --auth-brand-mid: #c2410c;
  --auth-brand-to: #ea580c;
  --auth-orb-a: rgba(249, 115, 22, 0.24);
  --auth-orb-b: rgba(251, 146, 60, 0.18);
  --auth-orb-c: rgba(234, 88, 12, 0.14);
  --auth-grid: rgba(234, 88, 12, 0.07);
  --auth-node: rgba(194, 65, 12, 0.2);
  background: linear-gradient(165deg, #fff1e8 0%, #fff7f2 42%, #fff4eb 72%, #fafafa 100%);
}

.auth-page.is-org {
  --auth-accent: #0f766e;
  --auth-accent-soft: #ccfbf1;
  --auth-brand-from: #134e4a;
  --auth-brand-mid: #0f766e;
  --auth-brand-to: #14b8a6;
  --auth-orb-a: rgba(20, 184, 166, 0.22);
  --auth-orb-b: rgba(45, 212, 191, 0.16);
  --auth-orb-c: rgba(13, 148, 136, 0.14);
  --auth-grid: rgba(15, 118, 110, 0.07);
  --auth-node: rgba(15, 118, 110, 0.2);
  background: linear-gradient(165deg, #e7f8f5 0%, #f2fbfa 42%, #eef8f7 72%, #f8fafc 100%);
}

.auth-page.is-committee {
  --auth-accent: #1e3a5f;
  --auth-accent-soft: #e2e8f0;
  --auth-brand-from: #0b1220;
  --auth-brand-mid: #1e293b;
  --auth-brand-to: #334155;
  --auth-orb-a: rgba(51, 65, 85, 0.2);
  --auth-orb-b: rgba(71, 85, 105, 0.14);
  --auth-orb-c: rgba(30, 41, 59, 0.12);
  --auth-grid: rgba(51, 65, 85, 0.08);
  --auth-node: rgba(51, 65, 85, 0.22);
  background: linear-gradient(165deg, #e8edf3 0%, #f1f4f7 42%, #eef2f6 72%, #f8fafc 100%);
}

.auth-backdrop {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: -1px;
  background-image:
    linear-gradient(var(--auth-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--auth-grid) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 40%, #000 20%, transparent 75%);
  opacity: 0.9;
}

.bg-mesh {
  position: absolute;
  inset: -20%;
  background:
    radial-gradient(42% 36% at 18% 22%, var(--auth-orb-a), transparent 70%),
    radial-gradient(38% 32% at 86% 18%, var(--auth-orb-b), transparent 68%),
    radial-gradient(46% 40% at 70% 82%, var(--auth-orb-c), transparent 70%);
  filter: blur(8px);
  animation: mesh-drift 14s ease-in-out infinite alternate;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(2px);
  will-change: transform;
}

.orb-a {
  top: 8%;
  left: 6%;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle at 35% 35%, color-mix(in srgb, var(--auth-accent) 35%, #fff), transparent 68%);
  animation: orb-float-a 11s ease-in-out infinite;
}

.orb-b {
  top: 58%;
  right: 4%;
  width: 280px;
  height: 280px;
  background: radial-gradient(circle at 40% 40%, color-mix(in srgb, var(--auth-accent) 28%, #fff), transparent 70%);
  animation: orb-float-b 13s ease-in-out infinite;
}

.orb-c {
  bottom: -4%;
  left: 32%;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--auth-accent) 22%, #fff), transparent 72%);
  animation: orb-float-c 10s ease-in-out infinite;
}

.bg-ring {
  position: absolute;
  border: 1px solid color-mix(in srgb, var(--auth-accent) 18%, transparent);
  border-radius: 50%;
  opacity: 0.55;
}

.ring-a {
  top: 12%;
  right: 10%;
  width: 160px;
  height: 160px;
  animation: ring-pulse 9s ease-in-out infinite;
}

.ring-b {
  bottom: 14%;
  left: 8%;
  width: 220px;
  height: 220px;
  border-style: dashed;
  opacity: 0.4;
  animation: ring-spin 28s linear infinite;
}

.bg-nodes {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.55;
}

.node-lines path {
  fill: none;
  stroke: var(--auth-node);
  stroke-width: 1.2;
  stroke-linecap: round;
  stroke-dasharray: 6 10;
  animation: dash-flow 18s linear infinite;
}

.node-dots circle {
  fill: color-mix(in srgb, var(--auth-accent) 55%, #fff);
  opacity: 0.55;
  animation: node-twinkle 4.5s ease-in-out infinite;
}

.node-dots circle:nth-child(2n) {
  animation-delay: 0.8s;
}

.node-dots circle:nth-child(3n) {
  animation-delay: 1.6s;
}

.auth-home {
  position: relative;
  z-index: 1;
  display: inline-flex;
  margin: 0 0 1rem;
  color: #334155;
  font-size: 0.92rem;
  font-weight: 600;
  text-decoration: none;
}

.auth-home:hover {
  color: var(--auth-accent);
  text-decoration: none;
}

.auth-shell {
  position: relative;
  z-index: 1;
  max-width: 920px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 0.92fr 1.08fr;
  overflow: hidden;
  border: 1px solid rgba(15, 39, 68, 0.12);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow:
    0 24px 60px rgba(15, 39, 68, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.55) inset;
  backdrop-filter: blur(14px) saturate(1.15);
  animation: shell-up 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.auth-brand {
  position: relative;
  padding: 2rem 1.6rem 1.8rem;
  color: #f8fafc;
  background: linear-gradient(
    160deg,
    var(--auth-brand-from) 0%,
    var(--auth-brand-mid) 48%,
    var(--auth-brand-to) 100%
  );
  overflow: hidden;
}

.brand-pattern {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.14) 1px, transparent 0),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, transparent 42%);
  background-size: 18px 18px, 100% 100%;
  mask-image: linear-gradient(180deg, #000 30%, transparent 95%);
  opacity: 0.7;
  pointer-events: none;
}

.brand-glow {
  position: absolute;
  inset: auto -30% -40% -20%;
  height: 70%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.22), transparent 65%);
  animation: glow-drift 8s ease-in-out infinite alternate;
  pointer-events: none;
}

.brand-inner {
  position: relative;
  z-index: 1;
}

.brand-mark {
  width: 52px;
  height: 52px;
  margin-bottom: 1.1rem;
  filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.2));
}

.brand-kicker {
  margin: 0 0 0.4rem;
  font-size: 0.78rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.85;
}

.auth-brand h1 {
  margin: 0 0 0.7rem;
  font-family: var(--auth-display);
  font-size: clamp(1.45rem, 2.4vw, 1.85rem);
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: 0.02em;
}

.brand-lead {
  margin: 0 0 1.25rem;
  font-size: 0.95rem;
  line-height: 1.55;
  color: rgba(241, 245, 249, 0.9);
  max-width: 18rem;
}

.brand-points {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
  font-size: 0.88rem;
  color: rgba(226, 232, 240, 0.95);
}

.brand-points li {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
}

.brand-points li::before {
  content: '';
  width: 0.45rem;
  height: 0.45rem;
  margin-top: 0.42rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
}

.auth-main {
  padding: 1.75rem 1.6rem 1.5rem;
  background: #fff;
}

.auth-head :deep(h2) {
  margin: 0 0 0.35rem;
  font-family: var(--auth-display);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--auth-ink);
}

.auth-head :deep(p) {
  margin: 0 0 1.15rem;
  color: #64748b;
  font-size: 0.92rem;
  line-height: 1.5;
}

.auth-body :deep(.field-block) {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding: 0.95rem 0.95rem 1rem;
  border: 1px solid #e8eef7;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfdff 0%, #f7faff 100%);
}

.auth-page.is-mentor .auth-body :deep(.field-block) {
  border-color: #ffedd5;
  background: linear-gradient(180deg, #fffdfb 0%, #fff7f0 100%);
}

.auth-page.is-org .auth-body :deep(.field-block) {
  border-color: #ccfbf1;
  background: linear-gradient(180deg, #fbfffe 0%, #f3fbfa 100%);
}

.auth-body :deep(.block-label) {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--auth-accent);
}

.auth-body :deep(.field) {
  display: grid;
  gap: 0.35rem;
  font-size: 0.86rem;
  color: #475569;
}

.auth-body :deep(.field input) {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border: 1px solid #d7e0ec;
  border-radius: 11px;
  background: #fff;
  color: var(--auth-ink);
  font: inherit;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.auth-body :deep(.field input:focus) {
  outline: none;
  border-color: var(--auth-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--auth-accent) 18%, transparent);
}

.auth-body :deep(.email-row),
.auth-body :deep(.field-pair),
.auth-body :deep(.auth-actions) {
  display: grid;
  gap: 0.55rem;
}

.auth-body :deep(.email-row) {
  grid-template-columns: 1fr auto;
}

.auth-body :deep(.field-pair),
.auth-body :deep(.auth-actions) {
  grid-template-columns: 1fr 1fr;
}

.auth-body :deep(.auth-actions:has(> :only-child)) {
  grid-template-columns: 1fr;
}

.auth-body :deep(.code-btn),
.auth-body :deep(.ghost-btn) {
  min-width: 7.2rem;
  padding: 0 0.9rem;
  border: 1px solid color-mix(in srgb, var(--auth-accent) 45%, #fff);
  border-radius: 11px;
  background: var(--auth-accent-soft);
  color: var(--auth-accent);
  font: inherit;
  font-weight: 600;
  font-size: 0.86rem;
  cursor: pointer;
  text-align: center;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, transform 0.15s ease;
}

.auth-body :deep(.code-btn:hover:not(:disabled)),
.auth-body :deep(.ghost-btn:hover) {
  filter: brightness(0.98);
  transform: translateY(-1px);
  text-decoration: none;
}

.auth-body :deep(.code-btn:disabled) {
  opacity: 0.65;
  cursor: not-allowed;
}

.auth-body :deep(.submit-btn) {
  width: 100%;
  margin-top: 0.15rem;
  padding: 0.85rem 1rem;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--auth-brand-mid), var(--auth-brand-to));
  color: #fff;
  font: inherit;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  box-shadow: 0 10px 24px color-mix(in srgb, var(--auth-accent) 28%, transparent);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}

.auth-body :deep(.submit-btn:hover:not(:disabled)) {
  transform: translateY(-1px);
  filter: brightness(1.03);
}

.auth-body :deep(.submit-btn:disabled) {
  opacity: 0.7;
  cursor: wait;
}

.auth-body :deep(.ok-hint) {
  margin: 0;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  background: #ecfdf5;
  color: #047857;
  font-size: 0.86rem;
  line-height: 1.45;
}

.auth-body :deep(.error) {
  margin: 0 0 0.5rem;
  color: #dc2626;
  font-size: 0.9rem;
}

.auth-body :deep(.back-choose) {
  display: inline-flex;
  margin: 0 0 0.85rem;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--auth-accent);
  font-size: 0.92rem;
  cursor: pointer;
}

.auth-body :deep(.back-choose:hover) {
  text-decoration: underline;
}

.auth-body :deep(.role-grid) {
  display: grid;
  gap: 0.7rem;
}

.auth-body :deep(.role-card) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3rem;
  width: 100%;
  padding: 1rem 1.05rem;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.auth-body :deep(.role-card:hover) {
  border-color: color-mix(in srgb, var(--auth-accent) 55%, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}

.auth-body :deep(.role-card strong) {
  font-size: 1.05rem;
  color: var(--auth-ink);
}

.auth-body :deep(.role-card span) {
  font-size: 0.9rem;
  line-height: 1.45;
  color: #64748b;
}

.auth-foot {
  margin-top: 1.05rem;
  color: #64748b;
  font-size: 0.9rem;
}

.auth-foot :deep(a) {
  color: var(--auth-accent);
  font-weight: 600;
}

.auth-foot :deep(.sep) {
  margin: 0 0.35rem;
  opacity: 0.45;
}

@keyframes page-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes shell-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes glow-drift {
  from {
    transform: translate3d(0, 0, 0) scale(1);
  }
  to {
    transform: translate3d(-8%, -6%, 0) scale(1.08);
  }
}

@keyframes mesh-drift {
  from {
    transform: translate3d(0, 0, 0) scale(1);
  }
  to {
    transform: translate3d(2%, -2%, 0) scale(1.04);
  }
}

@keyframes orb-float-a {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(18px, 28px, 0);
  }
}

@keyframes orb-float-b {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(-24px, -16px, 0);
  }
}

@keyframes orb-float-c {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(12px, -22px, 0) scale(1.08);
  }
}

@keyframes ring-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.45;
  }
  50% {
    transform: scale(1.08);
    opacity: 0.7;
  }
}

@keyframes ring-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes dash-flow {
  to {
    stroke-dashoffset: -160;
  }
}

@keyframes node-twinkle {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(1);
  }
  50% {
    opacity: 0.85;
    transform: scale(1.35);
  }
}

@media (max-width: 820px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .auth-brand {
    padding: 1.35rem 1.25rem 1.2rem;
  }

  .brand-lead,
  .brand-points {
    display: none;
  }

  .auth-brand h1 {
    font-size: 1.35rem;
  }

  .brand-mark {
    width: 40px;
    height: 40px;
    margin-bottom: 0.7rem;
  }

  .bg-nodes,
  .bg-ring {
    opacity: 0.35;
  }
}

@media (max-width: 560px) {
  .auth-page {
    margin: 0;
    padding: 0.85rem 0.75rem 2rem;
  }

  .auth-shell {
    border-radius: 16px;
  }

  .auth-main {
    padding: 1.25rem 1rem 1.15rem;
  }

  .auth-body :deep(.email-row),
  .auth-body :deep(.field-pair),
  .auth-body :deep(.auth-actions) {
    grid-template-columns: 1fr;
  }

  .orb-a,
  .orb-b {
    width: 140px;
    height: 140px;
  }

  .bg-nodes {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bg-mesh,
  .bg-orb,
  .bg-ring,
  .node-lines path,
  .node-dots circle,
  .brand-glow {
    animation: none !important;
  }
}
</style>
