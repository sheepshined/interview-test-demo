<template>
  <div>
    <TopNav back-text="返回首页" />
    <main style="max-width:1152px;margin:0 auto;padding:48px 24px;">
      <div style="display:flex;gap:48px;flex-wrap:wrap;">
        <div style="flex:2;min-width:300px;">
          <h1 style="font-size:24px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">上传你的简历</h1>
          <p style="font-size:14px;color:var(--text-muted);margin-bottom:32px;">支持 PDF 格式，AI 将自动解析简历内容并匹配适合的岗位</p>
          <div class="upload-zone" :class="{active:isDragging}" @click="triggerUpload" @dragover.prevent="isDragging=true" @dragleave="isDragging=false" @drop.prevent="handleDrop">
            <input ref="fileInput" type="file" accept=".pdf" hidden @change="handleFileSelect" />
            <div style="width:56px;height:56px;border-radius:14px;background:var(--bg-100);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
              <DSIcon name="file" :size="28" color="var(--brand-600)" />
            </div>
            <p style="font-size:14px;color:var(--text-muted);text-align:center;margin-bottom:4px;">拖拽文件到此处，或点击上传</p>
            <p style="font-size:12px;color:var(--text-faint);text-align:center;margin-bottom:16px;">支持 PDF 格式，最大 10MB</p>
            <span class="ds-btn ds-btn-outline" style="font-size:13px;padding:6px 16px;">浏览文件</span>
          </div>
          <div style="display:flex;align-items:center;gap:16px;margin:24px 0;">
            <div style="flex:1;height:1px;background:var(--border-default);"></div>
            <span style="font-size:12px;color:var(--text-faint);">或</span>
            <div style="flex:1;height:1px;background:var(--border-default);"></div>
          </div>
          <div style="margin-bottom:24px;">
            <label style="display:block;font-size:14px;font-weight:500;margin-bottom:8px;color:var(--text-primary);">直接粘贴简历内容</label>
            <textarea v-model="textContent" rows="6" placeholder="在此粘贴你的简历文本内容..." class="ds-input" style="resize:vertical;line-height:1.7;"></textarea>
            <button class="ds-btn ds-btn-outline" style="font-size:13px;padding:8px 16px;margin-top:8px;" @click="parseText" :disabled="!textContent.trim()">解析文本</button>
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
const tips = ['确保包含教育背景、实习经历和技能描述','最新的简历效果更好','支持中英文简历']
function triggerUpload() { fileInput.value?.click() }
function handleFileSelect(e) { if(e.target.files[0]) doUpload(e.target.files[0]) }
function handleDrop(e) { isDragging.value=false; if(e.dataTransfer.files[0]) doUpload(e.dataTransfer.files[0]) }
async function doUpload(file) { try { const r=await uploadResume(file); if(r.success) parsedData.value=r; else alert(r.message||'简历解析失败') } catch { alert('上传失败') } }
async function parseText() { try { const r=await parseTextResume(textContent.value); if(r.success) parsedData.value=r } catch { alert('解析失败') } }
function goToMatching() { sessionStorage.setItem('resumeData',JSON.stringify(parsedData.value)); router.push('/job-matching') }
</script>
<style scoped>
.upload-zone { border:2px dashed var(--border-default); border-radius:var(--radius-lg); background:var(--surface-muted); padding:40px 24px; display:flex; flex-direction:column; align-items:center; cursor:pointer; transition:border-color 0.2s; min-height:200px; justify-content:center; }
.upload-zone.active,.upload-zone:hover { border-color:var(--brand-600); }
</style>
