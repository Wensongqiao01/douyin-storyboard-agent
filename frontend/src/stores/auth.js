import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('token') || '')

  function login(username, password) {
    return new Promise((resolve, reject) => {
      // Mock auth — to be replaced with real API call
      if (username && password) {
        const mockUser = { id: 1, username, role: 'editor' }
        const mockToken = 'jwt-mock-' + Date.now()
        user.value = mockUser
        token.value = mockToken
        localStorage.setItem('user', JSON.stringify(mockUser))
        localStorage.setItem('token', mockToken)
        resolve(mockUser)
      } else {
        reject(new Error('用户名和密码不能为空'))
      }
    })
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('user')
    localStorage.removeItem('token')
  }

  return { user, token, login, logout }
})
