import './style.css';
import {createApp} from 'vue';
import VideoPlayer from './components/VideoPlayer.vue';
import Catalog from './components/Catalog.vue';
import SyncWorkbench from './components/admin/SyncWorkbench.vue';
import GlobalSearch from './components/GlobalSearch.vue';
import ContinueWatching from './components/ContinueWatching.vue';
import Recommendations from './components/Recommendations.vue';
import TitleRating from './components/TitleRating.vue';
import UploadWizard from './components/admin/UploadWizard.vue';
import FavoriteButton from "./components/FavoriteButton.vue";

document.addEventListener('DOMContentLoaded', () => {
    const favoriteMounts = document.querySelectorAll('.vue-favorite-button');
    favoriteMounts.forEach(mount => {
        createApp(FavoriteButton, {
            titleId: mount.dataset.titleId,
            initialState: mount.dataset.initialState,
            csrfToken: mount.dataset.csrf
        }).mount(mount);
    });
    const continueWatchingMount = document.getElementById('vue-continue-watching');
    if (continueWatchingMount) {
        createApp(ContinueWatching).mount('#vue-continue-watching');
    }
    const recommendationsMount = document.getElementById('vue-recommendations');
    if (recommendationsMount) {
        createApp(Recommendations).mount('#vue-recommendations');
    }
    const globalSearchMount = document.getElementById('vue-global-search');
    if (globalSearchMount) {
        const app = createApp(GlobalSearch);
        app.mount('#vue-global-search');
    }
    const catalogMount = document.getElementById('vue-catalog-mount');
    if (catalogMount) {
        const app = createApp(Catalog);
        app.mount('#vue-catalog-mount');
    }
    const titleRatingMount = document.getElementById('vue-title-rating');
    if (titleRatingMount) {
        createApp(TitleRating, {
            titleId: titleRatingMount.dataset.titleId,
            initialScore: titleRatingMount.dataset.initialScore,
            csrfToken: titleRatingMount.dataset.csrf
        }).mount('#vue-title-rating');
    }
    const playerMount = document.getElementById('vue-player-mount');
    if (playerMount) {
        const app = createApp(VideoPlayer, {
            contentId: playerMount.dataset.contentId,
            contentType: playerMount.dataset.contentType,
            titleId: playerMount.dataset.titleId,
            episodeId: playerMount.dataset.episodeId,
            startProgress: playerMount.dataset.startProgress,
            lastTrackGroup: playerMount.dataset.lastTrackGroup,
            lastAudioAsset: playerMount.dataset.lastAudioAsset,
            lastQuality: playerMount.dataset.lastQuality,
            prefAudio: playerMount.dataset.prefAudio,
            autoSkip: playerMount.dataset.autoSkip,
            csrfToken: playerMount.dataset.csrf
        });
        app.mount('#vue-player-mount');
    }

    const workbenchMount = document.getElementById('vue-workbench-mount');
    if (workbenchMount) {
        const app = createApp(SyncWorkbench, {
            objectId: workbenchMount.dataset.objectId,
            contentType: workbenchMount.dataset.contentType,
            csrfToken: workbenchMount.dataset.csrf
        });
        app.mount('#vue-workbench-mount');
    }

    const uploadWizardMount = document.getElementById('vue-upload-wizard-mount');
    if (uploadWizardMount) {
        const app = createApp(UploadWizard, {
            csrfToken: uploadWizardMount.dataset.csrf
        });
        app.mount('#vue-upload-wizard-mount');
    }
});