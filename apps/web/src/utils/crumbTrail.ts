/** 跨页延续的三层面包屑（sessionStorage）。 */

export type CrumbItem = {
  label: string
  to?: string
}

const KEY = 'ip_nav_trail_v1'

export function getStoredTrail(): CrumbItem[] {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return []
    const v = JSON.parse(raw) as unknown
    if (!Array.isArray(v)) return []
    return v
      .filter((x): x is CrumbItem => !!x && typeof x === 'object' && typeof (x as CrumbItem).label === 'string')
      .map((x) => ({ label: String(x.label), to: x.to ? String(x.to) : undefined }))
      .slice(-3)
  } catch {
    return []
  }
}

export function setStoredTrail(items: CrumbItem[]) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(items.slice(-3)))
  } catch {
    /* ignore quota */
  }
}

export function clearTrail() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}

/** 从列表页出发前写入父级路径，供下一页继承。 */
export function seedTrail(parents: CrumbItem[]) {
  setStoredTrail(
    parents
      .filter((p) => p?.label)
      .map((p) => ({ label: p.label, to: p.to }))
      .slice(-3),
  )
}

function toDisplay(full: CrumbItem[]): CrumbItem[] {
  const capped = full.slice(-3)
  setStoredTrail(capped)
  return capped.map((c, i) =>
    i === capped.length - 1 ? { label: c.label } : { label: c.label, to: c.to },
  )
}

/**
 * 当前页面包屑：继承上一页 trail，追加本页，最多 3 级。
 * `current.to` 必须是本页可回跳的路径（会写入 storage 供下一级使用）。
 */
export function resolveCrumbs(
  current: { label: string; to: string },
  fallbackParents: CrumbItem[] = [],
): CrumbItem[] {
  const stored = getStoredTrail()

  // 回到 trail 中已有页面：截断到该级
  const hit = stored.findIndex((p) => p.to && p.to === current.to)
  if (hit >= 0) {
    return toDisplay([
      ...stored.slice(0, hit),
      { label: current.label, to: current.to },
    ])
  }

  const last = stored[stored.length - 1]
  // 同页刷新 / 标题异步到位：更新当前级文案
  if (last?.to && last.to === current.to) {
    return toDisplay([...stored.slice(0, -1), { label: current.label, to: current.to }])
  }

  let parents = (stored.length ? stored : fallbackParents)
    .filter((p) => p.label)
    .map((p) => ({ label: p.label, to: p.to }))

  // 去掉与当前同 label 的尾部重复，避免「任务介绍 › 任务介绍」
  while (parents.length && parents[parents.length - 1]?.label === current.label) {
    parents = parents.slice(0, -1)
  }

  parents = parents.slice(-2)

  return toDisplay([...parents, { label: current.label, to: current.to }])
}
