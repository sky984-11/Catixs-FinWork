<template>
  <div class="resource-home">
    <section class="resource-home__head">
      <div>
        <span>Resource Desk</span>
        <h1>资源模块</h1>
        <p>面向销售的可售资源视图，集中查看可售服务器、线路价格与 IP 资源。</p>
      </div>
    </section>
    <div class="resource-home__grid">
      <RouterLink class="resource-home__card" to="/resource/free-devices">
        <TheIcon icon="mdi:server-plus-outline" :size="26" />
        <strong>可售服务器</strong>
        <span>按地区查看机柜管理里的可售服务器</span>
      </RouterLink>
      <RouterLink class="resource-home__card" to="/resource/zenlayer-pricing">
        <TheIcon icon="mdi:chart-line-variant" :size="26" />
        <strong>供应商比价</strong>
        <span>快速查询 SDN 线路报价参考</span>
      </RouterLink>
      <RouterLink class="resource-home__card" to="/resource/ipxo">
        <TheIcon icon="mdi:ip-network-outline" :size="26" />
        <strong>IPXO</strong>
        <span>展示已购买 IP 资源与月度价格</span>
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import TheIcon from '@/components/icon/TheIcon.vue'
</script>

<style scoped>
.resource-home {
  padding: 22px;
}

.resource-home__head {
  min-height: 170px;
  display: flex;
  align-items: flex-end;
  padding: 28px;
  border-radius: 8px;
  background: #0f172a;
  color: #fff;
}

.resource-home__head span,
.resource-home__head p,
.resource-home__card span {
  color: #94a3b8;
}

.resource-home__head h1 {
  margin: 6px 0;
  font-size: 32px;
}

.resource-home__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.resource-home__card {
  display: grid;
  gap: 10px;
  padding: 18px;
  min-height: 130px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  text-decoration: none;
}

.resource-home__card:hover {
  border-color: #94a3b8;
}

.resource-home__card strong {
  font-size: 18px;
}

@media (max-width: 900px) {
  .resource-home__grid {
    grid-template-columns: 1fr;
  }
}
</style>
