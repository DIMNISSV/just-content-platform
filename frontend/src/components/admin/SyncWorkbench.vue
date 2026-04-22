<script setup>
import {computed, onMounted, ref} from 'vue';

const props = defineProps({
  objectId: String,
  contentType: String,
  csrfToken: String
});

const assets = ref([]);
const isLoading = ref(true);

// State for new TrackGroup
const groupName = ref('Standard Version');
const selectedVideoId = ref('');
const additionalTracks = ref([]);

const fetchAssets = async () => {
  try {
    const res = await fetch('/api/v1/media/assets/');
    const data = await res.json();
    assets.value = data.results || data;
  } catch (e) {
    console.error("Failed to fetch assets", e);
  } finally {
    isLoading.value = false;
  }
};

const videoAssets = computed(() => assets.value.filter(a => a.type === 'VIDEO'));
const audioAssets = computed(() => assets.value.filter(a => a.type === 'AUDIO' || a.type === 'SUBTITLE'));

const addTrack = () => {
  additionalTracks.value.push({asset_id: '', language: 'RUS (Dub)', offset_ms: 0});
};

const removeTrack = (index) => {
  additionalTracks.value.splice(index, 1);
};

const saveWorkbench = async () => {
  if (!selectedVideoId.value) {
    alert("Please select a Base Video Asset.");
    return;
  }

  const payload = {
    name: groupName.value,
    video_asset_id: selectedVideoId.value,
    tracks: additionalTracks.value.filter(t => t.asset_id)
  };

  try {
    const res = await fetch(`/api/v1/content/workbench/save/${props.contentType}/${props.objectId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      alert("Track Group saved successfully!");
      window.location.href = `/admin/content/${props.contentType}/${props.objectId}/change/`;
    } else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to save"));
    }
  } catch (e) {
    console.error(e);
    alert("Network error while saving.");
  }
};

onMounted(() => {
  fetchAssets();
});
</script>

<template>
  <div class="bg-gray-900 text-gray-200 p-6 rounded-lg shadow-xl border border-gray-700">
    <div v-if="isLoading" class="text-center py-4">Loading Assets...</div>

    <div v-else class="space-y-6">
      <!-- 1. Basics -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-bold text-gray-400 mb-1">Version Name</label>
          <input v-model="groupName" type="text"
                 class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white">
        </div>
        <div>
          <label class="block text-sm font-bold text-gray-400 mb-1">Base Video Asset</label>
          <select v-model="selectedVideoId" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white">
            <option disabled value="">-- Select Video --</option>
            <option v-for="v in videoAssets" :key="v.id" :value="v.id">
              {{ v.original_name }} ({{ v.variants.length }} qualities) [ID: {{ v.id.substring(0,6) }}]
            </option>
          </select>
        </div>
      </div>

      <!-- 2. Additional Tracks -->
      <div class="bg-gray-800 p-4 rounded-lg border border-gray-700">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-bold text-white">Audio & Subtitle Tracks</h3>
          <button @click.prevent="addTrack"
                  class="bg-brand text-white px-3 py-1 rounded text-sm hover:bg-red-700 transition">
            + Add Track
          </button>
        </div>

        <div v-if="additionalTracks.length === 0" class="text-gray-500 text-sm italic">
          No additional tracks added. Native audio will be used.
        </div>

        <div v-for="(track, idx) in additionalTracks" :key="idx"
             class="flex items-end gap-4 mb-3 bg-gray-900 p-3 rounded">
          <div class="flex-1">
            <label class="block text-xs text-gray-400 mb-1">Asset</label>
            <select v-model="track.asset_id" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
              <option disabled value="">-- Select Track --</option>
              <option v-for="a in audioAssets" :key="a.id" :value="a.id">
                [{{ a.type }}] {{ a.original_name }} ({{ a.variants.length }} qual)
              </option>
            </select>
          </div>

          <div class="w-32">
            <label class="block text-xs text-gray-400 mb-1">Language</label>
            <input v-model="track.language" type="text"
                   class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
          </div>

          <div class="w-32">
            <label class="block text-xs text-gray-400 mb-1">Offset (ms)</label>
            <input v-model.number="track.offset_ms" type="number"
                   class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white">
          </div>

          <button @click.prevent="removeTrack(idx)" class="text-red-500 hover:text-red-400 p-2 text-xl font-bold">×
          </button>
        </div>
      </div>

      <!-- 3. Actions -->
      <div class="flex justify-end mt-6">
        <button @click.prevent="saveWorkbench"
                class="bg-green-600 text-white px-6 py-2 rounded font-bold hover:bg-green-500 transition shadow-lg">
          Save Track Group
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>