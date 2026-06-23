<template>
  <NoVncConsole
    :remote="String(route.query.remote || '')"
    :vmid="route.query.vmid || ''"
    :node="String(route.query.node || '')"
    :type="String(route.query.type || 'pve-qemu')"
  />
</template>

<script setup>
import { useRoute } from 'vue-router'
import NoVncConsole from './NoVncConsole.vue'

const route = useRoute()
</script>
