<template>
  <div>
    <TopNav back-text="返回首页" />
    <main style="max-width:1152px;margin:0 auto;padding:48px 24px;">
      <div style="display:flex;gap:48px;flex-wrap:wrap;">
        <div style="flex:2;min-width:300px;">
          <h1 style="font-size:24px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">上传你的简历</h1>
          <p style="font-size:14px;color:var(--text-muted);margin-bottom:32px;">支持 PDF 格式，AI 将自动解析简历内容并匹配适合的岗位</p>
          <div
            class="upload-zone"
            :class="{ active: isDragging, disabled: uploading }"
            @click="triggerUpload"
            @dragover.prevent="isDragging=true"
            @dragleave="isDragging=false"
            @drop.prevent="handleDrop"
          >
            <input ref="fileInput" type="file" accept=".pdf,application/pdf" hidden @change="handleFileSelect" />
            <div style="width:56px;height:56px;border-radius:14px;background:var(--bg-100);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
              <DSIcon v-if="!uploading" name="file" :size="28" color="var(--brand-600)" />
              <span v-else class="spinner"></span>
            </div>
            <p v-if="!uploading" style="font-size:14px;color:var(--text-muted);text-align:center;margin-bottom:4px;">拖拽文件到此处，或点击上传</p>
            <p v-else style="font-size:14px;color:var(--brand-600);text-align:center;margin-bottom:4px;font-weight:500;">正在解析简历，请稍候…</p>
            <p v-if="!uploading" style="font-size:12px;color:var(--text-faint);text-align:center;margin-bottom:16px;">支持 PDF 格式，最大 10MB</p>
            <p v-else style="font-size:12px;color:var(--text-faint);text-align:center;margin-bottom:16px;">AI 解析通常需要 10-20 秒</p>
            <span v-if="!uploading" class="ds-btn ds-btn-outline" style="font-size:13px;padding:6px 16px;">浏览文件</span>
          </div>

          <!-- 错误提示 -->
          <div v-if="errorMsg" class="alert alert-error">
            <DSIcon name="triangle-alert" :size="16" color="var(--danger)" />
            <span>{{ errorMsg }}</span>
          </div>

          <!-- 成功提示 -->
          <div v-if="parsedData && !uploading" class="alert alert-success">
            <DSIcon name="circle-check" :size="16" color="var(--success)" />
            <span>解析成功！{{ parsedData.name ? '识别到 ' + parsedData.name + '，' : '' }}提取 {{ (parsedData.skills||[]).length }} 项技能</span>
          </div>

          <div style="display:flex;align-items:center;gap:16px;margin:24px 0;">
            <div style="flex:1;height:1px;background:var(--border-default);"></div>
            <span style="font-size:12px;color:var(--text-faint);">或</span>
            <div style="flex:1;height:1px;background:var(--border-default);"></div>
          </div>
          <div style="margin-bottom:24px;">
            <label style="display:block;font-size:14px;font-weight:500;margin-bottom:8px;color:var(--text-primary);">直接粘贴简历内容</label>
            <textarea v-model="textContent" rows="6" placeholder="在此粘贴你的简历文本内容..." class="ds-input" style="resize:vertical;line-height:1.7;"></textarea>
            <button class="ds-btn ds-btn-outline" style="font-size:13px;padding:8px 16px;margin-top:8px;" @click="parseText" :disabled="!textContent.trim() || uploading">解析文本</button>
          </div>
          <button v-if="parsedData" class="ds-btn ds-btn-primary w-full" style="padding:14px;" @click="goToMatching">开始匹配 →</button>
          <p style="font-size:12px;color:var(--text-faint);text-align:center;margin-top:12px;">你的简历仅用于面试匹配，不会泄露给第三方</p>
        </div>
        <div style="flex:1;min-width:240px;">
          <div class="ds-card" style="padding:24px;">
            <h3 style="font-size:15px;font-weight:600;margin-bottom:16px;color:var(--text-primary);">上传建议</h3>
            <ul style="list-style:none;display:flex;flex-direction:column;gap:14px;">
              <li v-for="tip in tips" :key="tip" style="display:flex;align-items:flex-start;gap:10px;font-size:13px;color:var(--text-muted);line-height:1.5;">
                <span style="width:20px;height:20px;border-radius:6px;background:var(--bg-100);display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;">
                  <DSIcon name="check" :size="12" color="var(--success)" />
                </span>
                {{ tip }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { uploadResume, parseTextResume } from '../api'
import TopNav from '../components/TopNav.vue'
import DSIcon from '../components/DSIcon.vue'

const router = useRouter()
const fileInput = ref(null)
const isDragging = ref(false)
const textContent = ref('')
const parsedData = ref(null)
const uploading = ref(false)
const errorMsg = ref('')
const tips = ['确保包含教育背景、实习经历和技能描述', '最新的简历效果更好', '支持中英文简历']

const MAX_SIZE = 10 * 1024 * 1024 // 10MB

function triggerUpload() {
  if (uploading.value) return
  errorMsg.value = ''
  fileInput.value?.click()
}

function validateFile(file) {
  if (!file) return '请选择文件'
  const name = file.name.toLowerCase()
  const isPdf = name.endsWith('.pdf') || file.type === 'application/pdf'
  if (!isPdf) return '仅支持 PDF 文件'
  if (file.size === 0) return '文件为空，请重新选择'
  if (file.size > MAX_SIZE) return `文件过大 (${(file.size / 1024 / 1024).toFixed(1)}MB)，最大支持 10MB`
  return ''
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) doUpload(file)
  // 清空 input value 以便重复选择同一文件
  e.target.value = ''
}

function handleDrop(e) {
  isDragging.value = false
  if (uploading.value) return
  const file = e.dataTransfer.files[0]
  if (file) doUpload(file)
}

async function doUpload(file) {
  errorMsg.value = ''
  // 前端预校验
  const invalid = validateFile(file)
  if (invalid) {
    errorMsg.value = invalid
    return
  }

  uploading.value = true
  parsedData.value = null
  try {
    const r = await uploadResume(file)
    if (r && r.success) {
      parsedData.value = r
    } else {
      errorMsg.value = (r && r.message) || '简历解析失败'
    }
  } catch (err) {
    errorMsg.value = `上传失败: ${err.message || '未知错误'}`
    console.error('[上传简历] 异常:', err)
  } finally {
    uploading.value = false
  }
}

async function parseText() {
  errorMsg.value = ''
  if (uploading.value) return
  uploading.value = true
  try {
    const r = await parseTextResume(textContent.value)
    if (r && r.success) {
      parsedData.value = r
    } else {
      errorMsg.value = (r && r.message) || '解析失败'
    }
  } catch (err) {
    errorMsg.value = `解析失败: ${err.message || '未知错误'}`
    console.error('[解析文本] 异常:', err)
  } finally {
    uploading.value = false
  }
}

function goToMatching() {
  sessionStorage.setItem('resumeData', JSON.stringify(parsedData.value))
  router.push('/job-matching')
}
</script>
<style scoped>
.upload-zone {
  border: 2px dashed var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-muted);
  padding: 40px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: border-color 0.2s, opacity 0.2s;
  min-height: 200px;
  justify-content: center;
}
.upload-zone.active,
.upload-zone:hover {
  border-color: var(--brand-600);
}
.upload-zone.disabled {
  cursor: progress;
  opacity: 0.7;
  pointer-events: none;
}
.alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md, 10px);
  font-size: 13px;
  line-height: 1.5;
  margin-top: 16px;
}
.alert-error {
  background: rgba(220, 38, 38, 0.08);
  color: var(--danger, #dc2626);
  border: 1px solid rgba(220, 38, 38, 0.2);
}
.alert-success {
  background: rgba(16, 185, 129, 0.08);
  color: var(--success, #10b981);
  border: 1px solid rgba(16, 185, 129, 0.2);
}
.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--bg-100);
  border-top-color: var(--brand-600);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
