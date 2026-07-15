<script setup>
import {onMounted, ref} from 'vue';
import ProfilePreferences from './profile/ProfilePreferences.vue';
import ProfileWatchHistory from './profile/ProfileWatchHistory.vue';
import ProfileFavorites from './profile/ProfileFavorites.vue';

const props = defineProps({csrfToken: String});

const prefs = ref({language_code: 'rus', preferred_voiceovers: [], auto_skip_intro: false});
const history = ref([]);
const favorites = ref([]);
const isLoading = ref(true);

const fetchDashboardData = async () => {
  isLoading.value = true;
  try {
    const [prefRes, histRes, favRes] = await Promise.all([
      fetch('/api/v1/users/preferences/'),
      fetch('/api/v1/content/history/'),
      fetch('/api/v1/content/titles/favorites/')
    ]);

    if (prefRes.ok) {
      prefs.value = await prefRes.json();
    }
    if (histRes.ok) {
      history.value = await histRes.json();
    }
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

onMounted(fetchDashboardData);
</script>

<template>
  <div v-if="isLoading" class="flex justify-center py-20">
    <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
  </div>

  <div v-else class="flex flex-col md:flex-row gap-8">
    <aside class="w-full md:w-1/3 xl:w-1/4">
      <ProfilePreferences :initial-prefs="prefs" :csrf-token="csrfToken"/>
    </aside>

    <main class="w-full md:w-2/3 xl:w-3/4 space-y-12">
      <ProfileWatchHistory :history="history"/>
      <ProfileFavorites :favorites="favorites"/>
    </main>
  </div>
</template>