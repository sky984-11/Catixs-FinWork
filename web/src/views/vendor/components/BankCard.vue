<template>
    <n-card title="银行账户" class="bank-card">
        <div class="bank-content">
            <div class="left">
                <div>账户名：Chief Telecom Inc</div>
                <div>账号：053007505008</div>
                <div>银行：BANK OF TAIWAN</div>
                <div>SWIFT：BKTWTWTP053</div>
                <div>币种：USD</div>

                <n-space class="mt">
                    <n-button size="small">编辑</n-button>
                    <n-button size="small" type="error">删除</n-button>
                </n-space>
            </div>

            <div class="icon">🏦</div>
        </div>
    </n-card>
</template>

<style scoped>
.bank-content {
    display: flex;
    justify-content: space-between;
}

.left {
    line-height: 2;
}

.icon {
    font-size: 48px;
    opacity: 0.2;
}

.mt {
    margin-top: 10px;
}
</style>