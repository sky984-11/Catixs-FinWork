<script setup>
import { NButton, NTag } from 'naive-ui'
import { useRouter } from 'vue-router'

import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '项目看板文档' })

const router = useRouter()

const boardColumns = [
  { name: '规划中', desc: '资源准备、排期确认、等待项目启动。', icon: 'mdi:clipboard-text-clock-outline' },
  { name: '进行中', desc: '正在实施交付，重点关注进度、风险和子任务 ETA。', icon: 'mdi:rocket-launch-outline' },
  { name: '验收中', desc: '等待客户、内部或交付结果确认。', icon: 'mdi:clipboard-check-outline' },
  { name: '已完成', desc: '项目已结束，不再触发子任务提醒。', icon: 'mdi:check-circle-outline' },
]

const workflows = [
  '创建项目时填写客户、负责人、状态和 ETA。',
  '把交付动作拆成子任务，并为每个子任务设置负责人和 ETA。',
  '推进过程中拖拽进度条，勾选已完成的子任务。',
  '上传项目资料，或添加飞书文件、文件夹等外部链接。',
  '需要协同时，用共享功能把项目共享给相关用户。',
  '项目结束后把状态改为已完成，避免继续产生提醒。',
]

const reminders = [
  { title: '子任务临近提醒', desc: '未完成子任务距离 ETA 还有一天时发送飞书提醒。' },
  { title: '子任务到期提醒', desc: '未完成子任务到达 ETA 时再发送一次提醒。' },
  { title: '每日总结', desc: '每天 8:30 按负责人分别汇总规划中、进行中、验收中的相关项目，并通过用户手机号解析飞书 user_id 后推送。' },
  { title: '跳转链接', desc: '飞书中的项目和子任务标题可点击跳转，域名固定为 https://finwork.catixs.net。' },
]
</script>

<template>
  <CommonPage show-footer title="项目看板文档">
    <template #action>
      <NButton secondary round @click="router.push('/project-board')">
        <TheIcon icon="mdi:view-dashboard-outline" :size="18" class="mr-5" />
        返回项目看板
      </NButton>
    </template>

    <section class="doc-hero">
      <div>
        <NTag type="info" round>项目交付协作</NTag>
        <h1>项目看板使用指南</h1>
        <p>
          项目看板用于跟踪客户项目从规划、进行、验收到完成的全过程。它把负责人、客户、进度、ETA、子任务、讨论、文件和飞书提醒集中到一个页面，适合日常推进和早会同步。
        </p>
      </div>
      <div class="hero-card">
        <span>飞书每日总结链接</span>
        <strong>https://finwork.catixs.net</strong>
        <small>点击项目或子任务标题可直接跳转到对应详情。</small>
      </div>
    </section>

    <section class="doc-section">
      <div class="section-title">
        <TheIcon icon="mdi:view-kanban-outline" :size="22" />
        <h2>看板状态</h2>
      </div>
      <div class="state-grid">
        <article v-for="item in boardColumns" :key="item.name" class="state-card">
          <TheIcon :icon="item.icon" :size="24" />
          <strong>{{ item.name }}</strong>
          <p>{{ item.desc }}</p>
        </article>
      </div>
    </section>

    <section class="doc-section split">
      <article>
        <div class="section-title compact">
          <TheIcon icon="mdi:plus-box-outline" :size="22" />
          <h2>新增项目</h2>
        </div>
        <p>点击项目看板右上角的新增项目。项目名称、客户、负责人为必填项。客户下拉框支持中文、英文和拼音模糊搜索，并优先展示客户全称。</p>
        <div class="field-list">
          <span>项目编号</span>
          <span>合同编号</span>
          <span>截止日期</span>
          <span>预算信息</span>
          <span>项目说明</span>
        </div>
      </article>

      <article>
        <div class="section-title compact">
          <TheIcon icon="mdi:progress-pencil" :size="22" />
          <h2>项目进度</h2>
        </div>
        <p>打开项目详情后，可以拖拽进度条调整进度。低进度偏红色，中间逐步过渡到橙色和黄色，接近完成时变为绿色。拖拽后系统会自动保存。</p>
        <div class="progress-demo">
          <span class="bar"><i /></span>
          <strong>0% → 100%</strong>
        </div>
      </article>
    </section>

    <section class="doc-section split">
      <article>
        <div class="section-title compact">
          <TheIcon icon="mdi:checkbox-marked-circle-plus-outline" :size="22" />
          <h2>子任务</h2>
        </div>
        <p>每个项目可以创建多个子任务，用来拆分实际执行动作，例如确认资源、等待供应商回复、收发光信息、Patching、客户验收等。</p>
        <ul>
          <li>支持负责人、ETA、备注和完成状态。</li>
          <li>支持编辑、删除、回复讨论。</li>
          <li>子任务 ETA 会用于飞书临近和到期提醒。</li>
        </ul>
      </article>

      <article>
        <div class="section-title compact">
          <TheIcon icon="mdi:folder-link-outline" :size="22" />
          <h2>文件和链接</h2>
        </div>
        <p>项目和子任务都支持上传文件，也支持添加外部链接。外部链接适合飞书文档、飞书文件夹、共享盘目录等资料。</p>
        <ul>
          <li>链接必须以 http:// 或 https:// 开头。</li>
          <li>项目文件用于保存整体资料。</li>
          <li>子任务文件用于挂载具体交付动作的资料。</li>
        </ul>
      </article>
    </section>

    <section class="doc-section">
      <div class="section-title">
        <TheIcon icon="mdi:share-variant-outline" :size="22" />
        <h2>共享和权限</h2>
      </div>
      <div class="notice-band">
        <p>普通用户只能看到自己负责或被共享的项目，admin 可以看到所有项目。项目卡片上的共享图标可以把项目共享给一个或多个用户。</p>
      </div>
    </section>

    <section class="doc-section">
      <div class="section-title">
        <TheIcon icon="mdi:bell-ring-outline" :size="22" />
        <h2>飞书提醒</h2>
      </div>
      <div class="reminder-grid">
        <article v-for="item in reminders" :key="item.title">
          <strong>{{ item.title }}</strong>
          <p>{{ item.desc }}</p>
        </article>
      </div>
      <div class="notice-band mt-12">
        <p>飞书应用消息依赖系统用户列表中的手机号。维护用户手机号后，系统会用手机号获取飞书 user_id，再把每日总结、ETA 提醒、新项目和新子任务通知发送给对应负责人。</p>
      </div>
    </section>

    <section class="doc-section">
      <div class="section-title">
        <TheIcon icon="mdi:format-list-checks" :size="22" />
        <h2>推荐流程</h2>
      </div>
      <ol class="workflow-list">
        <li v-for="item in workflows" :key="item">{{ item }}</li>
      </ol>
    </section>

    <section class="doc-section faq">
      <div class="section-title">
        <TheIcon icon="mdi:frequently-asked-questions" :size="22" />
        <h2>常见问题</h2>
      </div>
      <article>
        <strong>为什么看不到某个项目？</strong>
        <p>普通用户只能看到自己负责或被共享的项目。需要项目负责人共享给你，或者由 admin 查看。</p>
      </article>
      <article>
        <strong>为什么子任务没有提醒？</strong>
        <p>可能是子任务已完成、项目已完成或归档、子任务没有 ETA、负责人没有维护手机号、手机号无法匹配飞书用户，或者该阶段提醒已经发送过。</p>
      </article>
      <article>
        <strong>为什么每日总结没有某个项目？</strong>
        <p>每日总结只包含规划中、进行中、验收中的相关项目，并按负责人分别发送。已完成或归档项目不会进入总结。</p>
      </article>
    </section>
  </CommonPage>
</template>

<style scoped>
.doc-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  align-items: stretch;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 22px;
}

.doc-hero h1 {
  margin: 14px 0 10px;
  color: #0f172a;
  font-size: 28px;
}

.doc-hero p,
.doc-section p,
.doc-section li {
  color: #475569;
  line-height: 1.7;
}

.hero-card {
  display: grid;
  align-content: center;
  gap: 8px;
  border-radius: 8px;
  background: #f8fafc;
  padding: 18px;
}

.hero-card span,
.hero-card small {
  color: #64748b;
}

.hero-card strong {
  color: #2563eb;
  font-size: 18px;
  word-break: break-all;
}

.doc-section {
  margin-top: 16px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 18px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  color: #0f172a;
}

.section-title h2 {
  margin: 0;
  font-size: 18px;
}

.section-title.compact {
  margin-bottom: 8px;
}

.state-grid,
.reminder-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.state-card,
.reminder-grid article,
.split > article,
.faq article {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
}

.state-card {
  display: grid;
  gap: 7px;
}

.state-card strong,
.reminder-grid strong,
.faq strong {
  color: #0f172a;
}

.state-card p,
.reminder-grid p,
.faq p {
  margin: 0;
}

.split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  border: 0;
  background: transparent;
  padding: 0;
}

.field-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.field-list span {
  border-radius: 999px;
  background: #eef2ff;
  color: #334155;
  font-size: 12px;
  padding: 5px 10px;
}

.progress-demo {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  margin-top: 14px;
}

.progress-demo .bar {
  overflow: hidden;
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
}

.progress-demo i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ef4444, #f97316, #eab308, #22c55e);
}

.notice-band {
  border-radius: 8px;
  background: #eff6ff;
  padding: 14px 16px;
}

.notice-band p {
  margin: 0;
}

.workflow-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 20px;
}

.faq {
  display: grid;
  gap: 10px;
}

.faq .section-title {
  margin-bottom: 4px;
}

@media (max-width: 960px) {
  .doc-hero,
  .split,
  .state-grid,
  .reminder-grid {
    grid-template-columns: 1fr;
  }
}
</style>
