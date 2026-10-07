<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Rail from './components/Rail.vue'
import Icon from './components/Icon.vue'
import { toastState } from './composables/useToast'

const route = useRoute()
const layout = computed(() => route.meta.layout || 'app')

function closeRail() {
  document.body.classList.remove('rail-open')
}
</script>

<template>
  <div v-if="layout === 'app'" class="shell">
    <Rail />
    <div class="rail-scrim" @click="closeRail"></div>
    <div class="main">
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </div>
  </div>

  <RouterView v-else v-slot="{ Component }">
    <Transition name="page" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>

  <!-- 全局吐司 -->
  <div class="toast-host" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toastState.list" :key="t.id" class="toast is-on">
        <span class="tag-ic">
          <Icon :name="t.type === 'ok' ? 'checkCircle' : (t.type === 'warn' ? 'alert' : t.type)" />
        </span>
        <span>{{ t.text }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>