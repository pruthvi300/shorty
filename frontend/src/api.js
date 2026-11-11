import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000',
  timeout: 10000,
})

export function errorMessage(error, fallback) {
  return error?.response?.data?.error || fallback
}

export default {
  listLinks: (page = 1) => http.get('/api/links', { params: { page } }).then((r) => r.data),
  createLink: (body) => http.post('/api/links', body).then((r) => r.data),
  deleteLink: (id) => http.delete(`/api/links/${id}`),
  summary: () => http.get('/api/analytics/summary').then((r) => r.data),
  linkAnalytics: (id, days = 7) => http.get(`/api/analytics/links/${id}`, { params: { days } }).then((r) => r.data),
}
