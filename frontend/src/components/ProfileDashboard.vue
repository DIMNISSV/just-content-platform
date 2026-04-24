<script setup>
import {onMounted, ref} from 'vue';

const props = defineProps({csrfToken: String});

const prefs = ref({preferred_language: 'RUS (Dub)', auto_skip_intro: false});
const isSaving = ref(false);
const saveMessage = ref('');

const history = ref([]);
const favorites = ref([]);
const isLoading = ref(true);

const formatTime = (ms) => {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const getWatchLink = (item) => {
  return item.episode ? `/watch/episode/${item.episode.id}/` : `/watch/${item.title.id}/`;
};

const fetchDashboardData = async () => {
  isLoading.value = true;
  try {
    const [prefRes, histRes, favRes] = await Promise.all([
      fetch('/api/v1/users/preferences/'),
      fetch('/api/v1/content/history/'),
      fetch('/api/v1/content/titles/favorites/')
    ]);

    if (prefRes.ok) prefs.value = await prefRes.json();
    if (histRes.ok) history.value = await histRes.json();
    if (favRes.ok) {
      const favData = await favRes.json();
      favorites.value = favData.results || favData;
    }
  } catch (e) {
    console.error("Dashboard data load failed", e);
  } finally {
    isLoading.value = false;
  }
};

const updatePreferences = async () => {
  isSaving.value = true;
  saveMessage.value = '';
  try {
    const res = await fetch('/api/v1/users/preferences/', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify(prefs.value)
    });
    if (res.ok) {
      saveMessage.value = 'Settings saved!';
      setTimeout(() => saveMessage.value = '', 3000);
    }
  } catch (e) {
    saveMessage.value = 'Error saving.';
  } finally {
    isSaving.value = false;
  }
};

onMounted(fetchDashboardData);
</script>

<template>
  <div v-if="isLoading" class="flex justify-center py-20">
    <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
  </div>

  <div v-else class="flex flex-col md:flex-row gap-8">
    <!-- Left Column: Settings -->
    <aside class="w-full md:w-1/3 xl:w-1/4">
      <div class="bg-card p-6 rounded-xl border border-gray-800 sticky top-24">
        <h2 class="text-xl font-black tracking-tighter mb-6 uppercase text-brand">Playback Settings</h2>

        <div class="space-y-6">
          <div>
            <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Preferred Audio Language</label>
            <input
                v-model="prefs.preferred_language"
                type="text"
                placeholder="e.g. RUS (Dub) or ENG"
                class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm"
            >
            <p class="text-[10px] text-gray-600 mt-1">Player will automatically select this track if available.</p>
          </div>

          <label class="flex items-center gap-3 cursor-pointer group">
            <div class="relative">
              <input type="checkbox" v-model="prefs.auto_skip_intro" class="sr-only">
              <div class="block bg-gray-800 w-10 h-6 rounded-full border border-gray-700 transition"
                   :class="prefs.auto_skip_intro ? 'bg-brand border-brand' : ''"></div>
              <div class="dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform"
                   :class="prefs.auto_skip_intro ? 'translate-x-4' : ''"></div>
            </div>
            <div class="text-sm font-bold text-gray-300 group-hover:text-white transition">Auto-Skip Intros</div>
          </label>

          <button
              @click="updatePreferences"
              :disabled="isSaving"
              class="w-full bg-gray-800 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded border border-gray-700 transition disabled:opacity-50"
          >
            {{ isSaving ? 'Saving...' : 'Save Settings' }}
          </button>

          <div v-if="saveMessage" class="text-xs font-bold text-green-500 text-center transition-opacity">
            {{ saveMessage }}
          </div>
        </div>
      </div>
    </aside>

    <!-- Right Column: Content -->
    <main class="w-full md:w-2/3 xl:w-3/4 space-y-12">

      <!-- History -->
      <section>
        <h2 class="text-2xl font-bold mb-6 tracking-tight border-l-4 border-gray-600 pl-3">History</h2>
        <div v-if="history.length === 0" class="text-gray-500 text-sm">No watch history yet.</div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <a v-for="item in history" :key="item.id" :href="getWatchLink(item)"
             class="group bg-gray-900 rounded-lg overflow-hidden border border-gray-800 hover:border-brand transition block">
            <div class="aspect-video relative bg-black">
              <img v-if="item.title.poster" :src="item.title.poster"
                   class="w-full h-full object-cover opacity-50 group-hover:opacity-70 transition-opacity">
              <div class="absolute bottom-2 right-2 bg-black/80 px-2 py-1 rounded text-xs font-bold text-white">
                {{ formatTime(item.progress_ms) }}
              </div>
            </div>
            <div class="p-4">
              <h3 class="text-sm font-bold text-white truncate">{{ item.title.name }}</h3>
              <p class="text-xs text-gray-400 mt-1 truncate">
                <template v-if="item.episode">S{{ item.episode.season_number }} E{{
                    item.episode.episode_number
                  }}
                </template>
                <template v-else>Movie</template>
              </p>
            </div>
          </a>
        </div>
      </section>

      <!-- Favorites -->
      <section>
        <h2 class="text-2xl font-bold mb-6 tracking-tight border-l-4 border-brand pl-3">My List</h2>
        <div v-if="favorites.length === 0" class="text-gray-500 text-sm">Your list is empty.</div>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
          <a v-for="title in favorites" :key="title.id" :href="`/watch/${title.id}/`" class="group block">
            <div class="aspect-[2/3] bg-gray-900 rounded-lg overflow-hidden mb-3 relative">
              <img v-if="title.poster" :src="title.poster" :alt="title.name"
                   class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
              <div class="absolute top-2 right-2 bg-brand px-2 py-1 rounded text-xs font-bold text-white">★
                {{ Number(title.rating_score).toFixed(1) }}
              </div>
            </div>
            <h3 class="text-sm font-semibold truncate text-gray-200 group-hover:text-white">{{ title.name }}</h3>
          </a>
        </div>
      </section>

    </main>
  </div>
</template>