<script setup>
import {onBeforeUnmount, onMounted, ref} from 'vue';
import WizardRawFiles from './wizard/WizardRawFiles.vue';
import WizardContentTree from './wizard/WizardContentTree.vue';
import StreamSelectorModal from './StreamSelectorModal.vue';

const props = defineProps({csrfToken: String});

const rawFiles = ref([]);
const contentTree = ref([]);
const isLoading = ref(true);
const activeUploads = ref([]);
let pollingInterval = null;

const showStreamModal = ref(false);
const selectedFileForModal = ref(null);

const fetchRawFiles = async () => {
  try {
    const res = await fetch('/api/v1/media/raw-files/');
    rawFiles.value = (await res.json()).results || [];
  } catch (e) {
    console.error("Failed to fetch raw files", e);
  }
};

const fetchData = async () => {
  isLoading.value = true;
  try {
    await fetchRawFiles();
    const treeRes = await fetch('/api/v1/content/tree/');
    contentTree.value = await treeRes.json();
  } catch (e) {
    console.error("Failed to fetch tree", e);
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  fetchData();
  pollingInterval = setInterval(() => {
    if (rawFiles.value.some(f => f.status === 'PENDING' || f.status === 'ANALYZING')) fetchRawFiles();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollingInterval) clearInterval(pollingInterval);
});
const handleCreateEpisode = async (payload) => {
  try {
    const res = await fetch('/api/v1/content/episodes/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': props.csrfToken},
      body: JSON.stringify(payload)
    });
    if (res.ok) await fetchData();
    else alert("Failed to create episode. Check if S/E already exists.");
  } catch (e) {
    console.error(e);
  }
};

// Обработка удаления версии
const handleDeleteGroup = async (groupId) => {
  if (!confirm("Are you sure? This will delete the version but keep the physical assets.")) return;
  try {
    const res = await fetch(`/api/v1/content/track-groups/${groupId}/`, {
      method: 'DELETE',
      headers: {'X-CSRFToken': props.csrfToken}
    });
    if (res.ok) await fetchData();
  } catch (e) {
    console.error(e);
  }
};

// Обработка удаления (отвязки) аудио
const handleDeleteTrack = async (linkId) => {
  if (!confirm("Remove this audio track from version?")) return;
  try {
    const res = await fetch(`/api/v1/content/additional-tracks/${linkId}/`, {
      method: 'DELETE',
      headers: {'X-CSRFToken': props.csrfToken}
    });
    if (res.ok) await fetchData();
  } catch (e) {
    console.error(e);
  }
};

// Обработка загрузки файлов с ПК
const handleUploadFiles = (files) => {
  files.forEach(file => {
    const uploadState = {name: file.name, progress: 0, status: 'uploading'};
    activeUploads.value.push(uploadState);

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/v1/media/raw-files/', true);
    xhr.setRequestHeader('X-CSRFToken', props.csrfToken);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) uploadState.progress = Math.round((e.loaded / e.total) * 100);
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        uploadState.status = 'done';
        fetchRawFiles();
        setTimeout(() => {
          activeUploads.value = activeUploads.value.filter(u => u !== uploadState);
        }, 3000);
      } else {
        uploadState.status = 'error';
      }
    };
    xhr.onerror = () => {
      uploadState.status = 'error';
    };
    xhr.send(formData);
  });
};

// Обработка броска файла на дерево
const handleAssignDrop = (dropData) => {
  const file = rawFiles.value.find(f => f.id === dropData.fileId);

  if (!file) return;
  if (file.status !== 'READY') {
    alert("This file is not ready for processing yet. Please wait for extraction.");
    return;
  }

  selectedFileForModal.value = {
    file: file,
    targetId: dropData.targetId,
    dropType: dropData.dropType,
    targetType: dropData.targetType,
    targetName: dropData.targetName
  };
  showStreamModal.value = true;
};

const confirmStreamSelection = async (selectedStreams, groupAuthor) => {
  const context = selectedFileForModal.value;
  showStreamModal.value = false;
  isLoading.value = true;

  try {
    const res = await fetch('/api/v1/content/assign-file/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': props.csrfToken},
      body: JSON.stringify({
        raw_file_id: context.file.id,
        target_id: context.targetId,
        drop_type: context.dropType,
        target_type: context.targetType,
        selected_streams: selectedStreams,
        group_author: groupAuthor
      })
    });

    if (res.ok) await fetchData();
    else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to assign streams"));
    }
  } catch (err) {
    console.error(err);
    alert("Network error occurred.");
  } finally {
    isLoading.value = false;
    selectedFileForModal.value = null;
  }
};
</script>

<template>
  <div class="flex h-[80vh] gap-4 text-gray-200 relative">
    <div v-if="isLoading && !showStreamModal && rawFiles.length === 0"
         class="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>

    <!-- Компонент левой колонки -->
    <WizardRawFiles
        :raw-files="rawFiles"
        :active-uploads="activeUploads"
        @upload-files="handleUploadFiles"
    />

    <!-- Компонент правой колонки -->
    <WizardContentTree
        :content-tree="contentTree"
        @assign-drop="handleAssignDrop"
        @create-episode="handleCreateEpisode"
        @delete-group="handleDeleteGroup"
        @delete-track="handleDeleteTrack"
    />

    <StreamSelectorModal
        v-if="showStreamModal && selectedFileForModal"
        :file="selectedFileForModal.file"
        :drop-type="selectedFileForModal.dropType"
        :target-name="selectedFileForModal.targetName"
        @close="showStreamModal = false; selectedFileForModal = null"
        @confirm="confirmStreamSelection"
    />
  </div>
</template>