<template>
  <div id="app">
    <header class="header">
      <div class="logo">
        <span class="logo-icon">🔗</span>
        <span>Shorty</span>
      </div>
      <div class="text-muted text-sm">URL Shortener & Analytics</div>
    </header>

    <main class="container">
      <!-- Create link -->
      <section class="card mb-lg">
        <div class="card-header">
          <h2 class="card-title">Shorten a URL</h2>
        </div>
        <form @submit.prevent="createLink">
          <div class="input-group">
            <input v-model.trim="form.url" type="text" inputmode="url" class="input"
                   placeholder="Paste your long URL here..." aria-label="Long URL" required />
            <button type="submit" class="btn btn-primary" :disabled="creating">
              {{ creating ? 'Creating...' : 'Shorten' }}
            </button>
          </div>
          <div class="input-group mt-md">
            <input v-model.trim="form.title" type="text" class="input" maxlength="255"
                   placeholder="Title (optional)" aria-label="Title" />
            <input v-model.trim="form.customCode" type="text" class="input narrow" maxlength="32"
                   pattern="[A-Za-z0-9_\-]{3,32}" title="3-32 letters, digits, - or _"
                   placeholder="Custom code" aria-label="Custom code" />
            <select v-model.number="form.expiresInDays" class="input narrow" aria-label="Expiry">
              <option :value="null">Never expires</option>
              <option :value="1">Expires in 1 day</option>
              <option :value="7">Expires in 7 days</option>
              <option :value="30">Expires in 30 days</option>
            </select>
          </div>
        </form>

        <p v-if="formError" class="notice notice-error" role="alert">{{ formError }}</p>

        <div v-if="createdLink" class="notice notice-success">
          <span>Link created:</span>
          <a :href="createdLink.short_url" target="_blank" rel="noopener" class="link-url">{{ createdLink.short_url }}</a>
          <button type="button" class="btn btn-secondary btn-sm" @click="copy(createdLink.short_url)">
            {{ copied ? 'Copied ✓' : 'Copy' }}
          </button>
        </div>
      </section>

      <!-- Summary -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_links }}</div>
          <div class="stat-label">Total Links</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_clicks }}</div>
          <div class="stat-label">Total Clicks</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.clicks_today }}</div>
          <div class="stat-label">Clicks Today (UTC)</div>
        </div>
      </div>

      <!-- Links -->
      <section class="card">
        <div class="card-header">
          <h2 class="card-title">Your Links</h2>
          <button type="button" class="btn btn-secondary btn-sm" @click="refresh">↻ Refresh</button>
        </div>

        <p v-if="loadError" class="notice notice-error" role="alert">{{ loadError }}</p>

        <div v-if="!loadError && links.length === 0" class="empty-state">
          <div class="empty-state-icon">🔗</div>
          <p>No links yet. Create your first short link above!</p>
        </div>

        <div v-else-if="links.length" class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Short Link</th>
                <th>Original URL</th>
                <th>Clicks</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="link in links" :key="link.id">
                <td>
                  <a :href="link.short_url" target="_blank" rel="noopener" class="link-url">{{ link.short_code }}</a>
                  <div v-if="link.title" class="text-muted text-sm">{{ link.title }}</div>
                </td>
                <td><span class="link-original" :title="link.original_url">{{ link.original_url }}</span></td>
                <td><span class="clicks-badge">📊 {{ link.click_count }}</span></td>
                <td class="text-muted text-sm">
                  {{ formatDate(link.created_at) }}
                  <div v-if="link.expires_at">expires {{ formatDate(link.expires_at) }}</div>
                </td>
                <td class="actions">
                  <button type="button" class="btn btn-secondary btn-sm" @click="openAnalytics(link)">Analytics</button>
                  <button type="button" class="btn btn-secondary btn-sm" @click="deleteLink(link)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="pages > 1" class="pager">
          <button type="button" class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="goToPage(page - 1)">‹ Prev</button>
          <span class="text-muted text-sm">Page {{ page }} of {{ pages }}</span>
          <button type="button" class="btn btn-secondary btn-sm" :disabled="page >= pages" @click="goToPage(page + 1)">Next ›</button>
        </div>
      </section>

      <!-- Analytics -->
      <section v-if="selectedLink" class="card mt-md">
        <div class="card-header">
          <h2 class="card-title">Analytics: {{ selectedLink.short_code }}</h2>
          <div class="actions">
            <select v-model.number="days" class="input narrow" aria-label="Period" @change="loadAnalytics">
              <option :value="7">Last 7 days</option>
              <option :value="30">Last 30 days</option>
              <option :value="90">Last 90 days</option>
            </select>
            <button type="button" class="btn btn-secondary btn-sm" @click="closeAnalytics">✕ Close</button>
          </div>
        </div>

        <p v-if="analyticsError" class="notice notice-error" role="alert">{{ analyticsError }}</p>

        <div class="grid-2">
          <div class="card">
            <h3 class="card-title text-sm">Clicks Over Time ({{ analytics.total_clicks ?? 0 }} total)</h3>
            <div class="chart-container">
              <canvas ref="chartCanvas"></canvas>
            </div>
          </div>

          <div class="card">
            <h3 class="card-title text-sm">Device Breakdown</h3>
            <div v-for="device in analytics.device_breakdown || []" :key="device.device" class="mb-md">
              <div class="bar-label">
                <span>{{ device.device }}</span>
                <span class="text-muted">{{ device.count }} clicks</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: percentage(device.count) + '%' }"></div>
              </div>
            </div>
            <div v-if="!analytics.device_breakdown?.length" class="text-muted text-center">No clicks in this period</div>
          </div>
        </div>

        <div class="card mt-md">
          <h3 class="card-title text-sm mb-md">Top Referrers</h3>
          <div v-for="r in analytics.top_referrers || []" :key="r.referrer" class="referrer-row">
            <span class="link-original" :title="r.referrer">{{ r.referrer }}</span>
            <span class="clicks-badge">{{ r.count }}</span>
          </div>
          <div v-if="!analytics.top_referrers?.length" class="text-muted text-center">No referrer data yet</div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { CategoryScale, Chart, LinearScale, LineController, LineElement, PointElement } from 'chart.js'
import api, { errorMessage } from './api'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale)

const form = reactive({ url: '', title: '', customCode: '', expiresInDays: null })
const creating = ref(false)
const formError = ref('')
const createdLink = ref(null)
const copied = ref(false)

const links = ref([])
const page = ref(1)
const pages = ref(1)
const loadError = ref('')
const stats = ref({ total_links: 0, total_clicks: 0, clicks_today: 0 })

const selectedLink = ref(null)
const analytics = ref({})
const analyticsError = ref('')
const days = ref(7)
const chartCanvas = ref(null)
let chart = null

async function loadLinks() {
  try {
    const data = await api.listLinks(page.value)
    links.value = data.links
    pages.value = Math.max(data.pages, 1)
    if (page.value > pages.value) {
      page.value = pages.value
      return loadLinks()
    }
    loadError.value = ''
  } catch (error) {
    loadError.value = errorMessage(error, 'Could not load links. Is the API running?')
  }
}

async function loadStats() {
  try {
    stats.value = await api.summary()
  } catch {
    // The links list already reports connectivity problems.
  }
}

function refresh() {
  loadLinks()
  loadStats()
}

function goToPage(n) {
  page.value = n
  loadLinks()
}

async function createLink() {
  creating.value = true
  formError.value = ''
  createdLink.value = null
  copied.value = false
  try {
    createdLink.value = await api.createLink({
      url: form.url,
      title: form.title || undefined,
      custom_code: form.customCode || undefined,
      expires_in_days: form.expiresInDays ?? undefined,
    })
    Object.assign(form, { url: '', title: '', customCode: '', expiresInDays: null })
    page.value = 1
    refresh()
  } catch (error) {
    formError.value = errorMessage(error, 'Failed to create link')
  } finally {
    creating.value = false
  }
}

async function deleteLink(link) {
  if (!window.confirm(`Delete ${link.short_code}? It will stop redirecting.`)) return
  try {
    await api.deleteLink(link.id)
    if (selectedLink.value?.id === link.id) closeAnalytics()
    refresh()
  } catch (error) {
    loadError.value = errorMessage(error, 'Failed to delete link')
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    formError.value = 'Could not copy automatically. Select the link and copy it manually.'
  }
}

async function openAnalytics(link) {
  selectedLink.value = link
  await loadAnalytics()
}

async function loadAnalytics() {
  analyticsError.value = ''
  try {
    analytics.value = await api.linkAnalytics(selectedLink.value.id, days.value)
    await nextTick()
    renderChart()
  } catch (error) {
    analyticsError.value = errorMessage(error, 'Failed to load analytics')
  }
}

function closeAnalytics() {
  chart?.destroy()
  chart = null
  selectedLink.value = null
  analytics.value = {}
}

function renderChart() {
  if (!chartCanvas.value) return
  chart?.destroy()
  const points = analytics.value.clicks_by_day || []
  const css = getComputedStyle(document.documentElement)
  const accent = css.getPropertyValue('--accent').trim() || '#6366f1'
  const muted = css.getPropertyValue('--text-muted').trim() || '#94a3b8'
  chart = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      labels: points.map((p) => p.date),
      datasets: [{ label: 'Clicks', data: points.map((p) => p.count), borderColor: accent, fill: false, tension: 0.3 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { color: muted, precision: 0 }, grid: { color: 'rgba(148,163,184,0.15)' } },
        x: { ticks: { color: muted }, grid: { display: false } },
      },
    },
  })
}

function percentage(count) {
  const total = analytics.value.total_clicks || 1
  return Math.round((count / total) * 100)
}

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString() : '-'
}

onMounted(refresh)
onBeforeUnmount(() => chart?.destroy())
</script>

<style scoped>
.narrow { max-width: 180px; }
.actions { display: flex; gap: 0.5rem; align-items: center; }
.notice { margin-top: 1rem; padding: 0.75rem 1rem; border-radius: var(--radius-md); display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
.notice-error { color: var(--error); background: rgba(239, 68, 68, 0.1); border: 1px solid var(--error); }
.notice-success { color: var(--success); background: rgba(16, 185, 129, 0.1); border: 1px solid var(--success); }
.pager { display: flex; gap: 1rem; justify-content: center; align-items: center; margin-top: 1rem; }
.bar-label { display: flex; justify-content: space-between; }
.bar-track { background: var(--bg-primary); height: 8px; border-radius: 4px; margin-top: 4px; }
.bar-fill { background: var(--accent); height: 100%; border-radius: 4px; }
.referrer-row { display: flex; justify-content: space-between; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
@media (max-width: 640px) {
  .input-group { flex-wrap: wrap; }
  .narrow { max-width: none; }
}
</style>
