import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url) {
  const isConnected = ref(false)
  const lastMessage = ref(null)
  const error = ref(null)

  let socket = null
  let reconnectTimeout = null
  let heartbeatInterval = null
  let reconnectAttempts = 0
  const maxReconnectDelay = 30000
  const heartbeatMs = 25000 // Send heartbeat every 25s to keep connection alive

  const messageHandlers = new Set()

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatInterval = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'ping' }))
      }
    }, heartbeatMs)
  }

  function stopHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }

  function connect() {
    try {
      socket = new WebSocket(url)

      socket.onopen = () => {
        console.log('[WS] Connected')
        isConnected.value = true
        error.value = null
        reconnectAttempts = 0
        startHeartbeat()
      }

      socket.onclose = () => {
        console.log('[WS] Disconnected')
        isConnected.value = false
        stopHeartbeat()
        scheduleReconnect()
      }

      socket.onerror = (e) => {
        console.error('[WS] Error:', e)
        error.value = 'Connection error'
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          lastMessage.value = data
          messageHandlers.forEach(handler => handler(data))
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }
    } catch (e) {
      console.error('[WS] Connection failed:', e)
      error.value = 'Failed to connect'
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimeout) return

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay)
    console.log(`[WS] Reconnecting in ${delay}ms...`)

    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null
      reconnectAttempts++
      connect()
    }, delay)
  }

  function send(data) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(data))
    } else {
      console.warn('[WS] Cannot send - not connected')
    }
  }

  function onMessage(handler) {
    messageHandlers.add(handler)
    return () => messageHandlers.delete(handler)
  }

  function disconnect() {
    stopHeartbeat()
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    if (socket) {
      socket.close()
      socket = null
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    lastMessage,
    error,
    send,
    onMessage,
    disconnect
  }
}
