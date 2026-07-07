console.log("Sanity check");

fetch("/config")
    .then((result) => {return result.json;})
    .then((data) => {
        const stripe = Stripe(data.publicKey);
    });

let players = {};

function onYouTubeIframeAPIReady() {
    document.querySelectorAll('.yt-player-iframe').forEach(iframe => {
        players[iframe.id] = new YT.Player(iframe.id, {
            events: {
                'onReady': function(event) {
                    event.target.mute();
                }
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // Searchfunction for home
    const gameSearch = document.getElementById('gameSearch');
    if (gameSearch) {
        gameSearch.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase().trim();
            const items = document.querySelectorAll('.game-item');
            let visibleCount = 0;

            items.forEach(item => {
                if (item.getAttribute('data-title').includes(query)) {
                    item.classList.remove('d-none');
                    visibleCount++;
                } else {
                    item.classList.add('d-none');
                }
            });

            const noMatchMsg = document.getElementById('noMatchMessage');
            if (noMatchMsg) {
                if (visibleCount === 0 && items.length > 0) {
                    noMatchMsg.classList.remove('d-none');
                } else {
                    noMatchMsg.classList.add('d-none');
                }
            }
        });
    }

    // Filtering for the store
    const storeSearch = document.getElementById('storeSearch');
    const genreFilter = document.getElementById('genreFilter');
    const tagFilter = document.getElementById('tagFilter');
    const priceFilter = document.getElementById('priceFilter');
    const saleFilter = document.getElementById('saleFilter');
    const gameItems = document.querySelectorAll('.store-game-item');
    const storeNoMatchMsg = document.getElementById('storeNoMatchMessage');

    function filterGames() {
        const query = storeSearch.value.toLowerCase().trim();
        const genre = genreFilter.value;
        const tagQuery = tagFilter.value.toLowerCase().trim();
        const maxPrice = parseFloat(priceFilter.value);
        const onlySale = saleFilter.checked;
        let matches = 0;

        gameItems.forEach(item => {
            const itemTitle = item.getAttribute('data-title');
            const itemGenre = item.getAttribute('data-genre');
            const itemPrice = parseFloat(item.getAttribute('data-price'));
            const itemIsSale = item.getAttribute('data-sale') === 'true';
            const itemTags = JSON.parse(item.getAttribute('data-tags') || "[]");

            let matchTitle = itemTitle.includes(query);
            let matchGenre = (genre === 'all' || itemGenre === genre);
            let matchPrice = (isNaN(maxPrice) || itemPrice <= maxPrice);
            let matchSale = (!onlySale || itemIsSale);
            let matchTag = (tagQuery === '' || itemTags.some(t => t.includes(tagQuery)));

            if (matchTitle && matchGenre && matchPrice && matchSale && matchTag) {
                item.classList.remove('d-none');
                matches++;
            } else {
                item.classList.add('d-none');
            }
        });

        if (storeNoMatchMsg) {
            if (matches === 0 && gameItems.length > 0) {
                storeNoMatchMsg.classList.remove('d-none');
            } else {
                storeNoMatchMsg.classList.add('d-none');
            }
        }
    }

    if (storeSearch && genreFilter && tagFilter && priceFilter && saleFilter) {
        storeSearch.addEventListener('input', filterGames);
        genreFilter.addEventListener('change', filterGames);
        tagFilter.addEventListener('input', filterGames);
        priceFilter.addEventListener('input', filterGames);
        saleFilter.addEventListener('change', filterGames);
    }

    // Hover for home and store
    document.querySelectorAll('.game-card, .home-sale-card').forEach(card => {
        const videoType = card.getAttribute('data-video-type');
        if (!videoType || videoType === 'none') return;

        card.addEventListener('mouseenter', function() {
            if (videoType === 'youtube') {
                const ytId = card.getAttribute('data-yt-id');
                if (players[ytId] && typeof players[ytId].playVideo === 'function') {
                    players[ytId].playVideo();
                }
            } else if (videoType === 'local') {
                const video = card.querySelector('video');
                if (video) video.play();
            }
        });

        card.addEventListener('mouseleave', function() {
            if (videoType === 'youtube') {
                const ytId = card.getAttribute('data-yt-id');
                if (players[ytId] && typeof players[ytId].pauseVideo === 'function') {
                    players[ytId].pauseVideo();
                }
            } else if (videoType === 'local') {
                const video = card.querySelector('video');
                if (video) video.pause();
            }
        });
    });
});