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
import ProfileDashboard from "./components/ProfileDashboard.vue";
import SimilarTitles from './components/SimilarTitles.vue';
import TaxonomyManager from "./components/admin/TaxonomyManager.vue";

function getCsrfToken() {
    const match = document.cookie.match(new RegExp('(^| )csrftoken=([^;]+)'));
    return match ? match[2] : '';
}

async function handleGuestMerge() {
    const guestId = localStorage.getItem('jcp_guest_id');
    if (!guestId) return;

    try {
        const response = await fetch('/api/v1/recommendations/merge-guest/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({guest_id: guestId})
        });

        if (response.ok) {
            console.log("Guest profile merged successfully");
            localStorage.removeItem('jcp_guest_id');
        } else if (response.status === 401 || response.status === 403) {
            // User is not authenticated, keep the guest ID
        }
    } catch (e) {
        console.error("Error during guest profile merge:", e);
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    await handleGuestMerge();

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
        createApp(GlobalSearch).mount('#vue-global-search');
    }

    const catalogMount = document.getElementById('vue-catalog-mount');
    if (catalogMount) {
        createApp(Catalog).mount('#vue-catalog-mount');
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
        createApp(VideoPlayer, {
            contentId: playerMount.dataset.contentId,
            contentType: playerMount.dataset.contentType,
            titleId: playerMount.dataset.titleId,
            episodeId: playerMount.dataset.episodeId,
            startProgress: playerMount.dataset.startProgress,
            lastTrackGroup: playerMount.dataset.lastTrackGroup,
            lastAudioAsset: playerMount.dataset.lastAudioAsset,
            lastAudioTrackName: playerMount.dataset.lastAudioTrackName,
            lastQuality: playerMount.dataset.lastQuality,
            languageCode: playerMount.dataset.languageCode,
            preferredVoiceovers: playerMount.dataset.preferredVoiceovers,
            autoSkip: playerMount.dataset.autoSkip,
            csrfToken: playerMount.dataset.csrf,
            sessionToken: playerMount.dataset.sessionToken,
            pluginScriptUrl: playerMount.dataset.pluginScriptUrl
        }).mount('#vue-player-mount');
    }

    const similarTitlesMount = document.getElementById('vue-similar-titles');
    if (similarTitlesMount) {
        createApp(SimilarTitles, {
            titleId: similarTitlesMount.dataset.titleId
        }).mount('#vue-similar-titles');
    }

    const profileMount = document.getElementById('vue-profile-mount');
    if (profileMount) {
        createApp(ProfileDashboard, {
            csrfToken: profileMount.dataset.csrf
        }).mount('#vue-profile-mount');
    }

    const workbenchMount = document.getElementById('vue-workbench-mount');
    if (workbenchMount) {
        createApp(SyncWorkbench, {
            objectId: workbenchMount.dataset.objectId,
            contentType: workbenchMount.dataset.contentType,
            csrfToken: workbenchMount.dataset.csrf
        }).mount('#vue-workbench-mount');
    }

    const uploadWizardMount = document.getElementById('vue-upload-wizard-mount');
    if (uploadWizardMount) {
        createApp(UploadWizard, {
            csrfToken: uploadWizardMount.dataset.csrf
        }).mount('#vue-upload-wizard-mount');
    }

    const taxonomyManagerMount = document.getElementById('vue-taxonomy-manager-mount');
    if (taxonomyManagerMount) {
        createApp(TaxonomyManager, {
            csrfToken: taxonomyManagerMount.dataset.csrf
        }).mount('#vue-taxonomy-manager-mount');
    }
});