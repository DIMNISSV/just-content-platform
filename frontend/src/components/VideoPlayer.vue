<script setup>
import {ref, onMounted} from 'vue';

const props = defineProps(['contentId', 'contentType']);
const manifest = ref(null);
const activeSource = ref(null);

const fetchManifest = async () => {
  try {
    const response = await fetch(`/api/v1/player/manifest/${props.contentType}/${props.contentId}/`);
    manifest.value = await response.json();
    if (manifest.value.sources.length > 0) {
      // Берем первый доступный видео-источник
      activeSource.value = manifest.value.sources.find(s => s.type === 'VIDEO');
    }
  } catch (e) {
    console.error("Failed to load manifest", e);
  }
};

onMounted(() => {
  fetchManifest();
});
</script>

<template>
  <div class="relative w-full h-full bg-black">
    <video
        v-if="activeSource"
        :src="activeSource.storage_path"
        controls
        class="w-full h-full"
    ></video>
    <div v-else class="flex items-center justify-center h-full text-gray-500">
      No playback sources available
    </div>
  </div>
</template>