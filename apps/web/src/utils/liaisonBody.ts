export type LiaisonFile = {
  type: 'image' | 'file' | 'table'
  url?: string
  name?: string
  rows?: string[][]
}

export type LiaisonBody = { text: string; files: LiaisonFile[] }

export function packLiaison(text: string, files: LiaisonFile[]): string {
  const words = text.trim()
  if (!files.length) return words
  return JSON.stringify({ v: 1, text: words, files })
}

export function unpackLiaison(body: string): LiaisonBody {
  const raw = body || ''
  if (!raw.startsWith('{')) return { text: raw, files: [] }
  try {
    const data = JSON.parse(raw) as { v?: number; text?: string; files?: LiaisonFile[] }
    if (data?.v === 1) return { text: data.text || '', files: data.files || [] }
  } catch {
    /* 旧消息是纯文字 */
  }
  return { text: raw, files: [] }
}
