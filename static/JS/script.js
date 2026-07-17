console.log("Sanity check");


let players = {};
// yea boy thats just keeping track of all the youtube instances
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

//I had two DOMContentLoader before, so I merged them into one
document.addEventListener('DOMContentLoaded', () => {

    document.querySelectorAll('.vote-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const reviewId = btn.getAttribute('data-review-id');
            const voteType = btn.getAttribute('data-vote-type');
            fetch(`/vote_review/${reviewId}/${voteType}`, { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    btn.closest('.card-body').querySelector('.helpful-count').textContent = data.helpful;
                    btn.closest('.card-body').querySelector('.funny-count').textContent = data.funny;
                })
                .catch(err => console.error("Vote Mistake:", err));
        });
    });

    // ---- Wishlist Herz-Buttons (Store-Cards, Home-Cards, Detail-Seite, Wishlist-Seite) ----
    document.querySelectorAll('.wishlist-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const gameId = btn.getAttribute('data-game-id');

            fetch(`/toggle_wishlist/${gameId}`, { method: 'POST' })
                .then(res => {
                    if (res.status === 401 || res.redirected) {
                        // get back to your login!
                        window.location.href = "/login";
                        return null;
                    }
                    return res.json();
                })
                .then(data => {
                    if (!data) return;

                    const icon = btn.querySelector('i');
                    if (data.on_wishlist) {
                        btn.classList.add('active');
                        icon.classList.remove('bi-heart');
                        icon.classList.add('bi-heart-fill');
                    } else {
                        btn.classList.remove('active');
                        icon.classList.remove('bi-heart-fill');
                        icon.classList.add('bi-heart');
                    }

                    // when deleting it from the wishlist never see it again on the page
                    if (!data.on_wishlist && document.getElementById('wishlistGrid')) {
                        const card = btn.closest('.wishlist-item');
                        if (card) {
                            card.remove();
                            const grid = document.getElementById('wishlistGrid');
                            if (grid && grid.querySelectorAll('.wishlist-item').length === 0) {
                                const emptyMsg = document.getElementById('emptyWishlistMessage');
                                if (emptyMsg) emptyMsg.classList.remove('d-none');
                            }
                        }
                    }
                })
                .catch(err => console.error("Wishlist Fehler:", err));
        });
    });

    //  Stripe checkout
    fetch("/config")
        .then((result) => result.json())
        .then((data) => {
            const stripe = Stripe(data.publicKey);

            const submitBtn = document.querySelector("#submitBtn");
            // I think I fixed a bug here, not sure if it's the same as the one I had before
            if (submitBtn) {
                submitBtn.addEventListener("click", (e) => {
                    e.preventDefault();
                    const gameId = e.target.getAttribute("data-game-id");
                    fetch(`/create-checkout-session/${gameId}`)
                        .then((result) => result.json())
                        .then((data) => {
                            return stripe.redirectToCheckout({ sessionId: data.sessionId });
                        })
                        .catch((err) => { console.error("Stripe Fehler:", err); });
                });
            }
        });

    // ---- Sale countdown timers ----
    // Yea for some reason I had two timers before, and one just
    //blew away the memory and CPU usage. Should be fixed now.
    const timerElements = document.querySelectorAll(".timer");
    timerElements.forEach(timerElement => {
        const dateStr = timerElement.getAttribute("data-end");
        if (!dateStr) return; // skip when no date

        const endDate = new Date(dateStr).getTime();

        const interval = setInterval(() => {
            const now = new Date().getTime();
            const distance = endDate - now;

            if (distance < 0) {
                clearInterval(interval);
                timerElement.innerHTML = "SALE ENDED";
                return;
            }

            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            const display = timerElement.querySelector(".countdown");
            if (display) {
                display.innerHTML = `${days}d ${hours}h ${minutes}m ${seconds}s`;
            }
        }, 1000);
    });

    // ---- Searchfunction for home ----
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

    // ---- Filtering for the store (multi-select genres/tags + price range) ----
    const storeSearch = document.getElementById('storeSearch');
    const genreCheckboxes = document.querySelectorAll('.genre-checkbox');
    const tagCheckboxes = document.querySelectorAll('.tag-checkbox');
    const priceMinFilter = document.getElementById('priceMinFilter');
    const priceMaxFilter = document.getElementById('priceMaxFilter');
    const saleFilter = document.getElementById('saleFilter');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    const gameItems = document.querySelectorAll('.store-game-item');
    const genreHeadings = document.querySelectorAll('.genre-heading');
    const storeNoMatchMsg = document.getElementById('storeNoMatchMessage');
    const genreActiveCount = document.getElementById('genreActiveCount');
    const tagActiveCount = document.getElementById('tagActiveCount');

    function getCheckedValues(checkboxes) {
        return Array.from(checkboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value.toLowerCase());
    }

    function updateActiveCountBadge(badgeEl, count) {
        if (!badgeEl) return;
        if (count > 0) {
            badgeEl.textContent = `(${count})`;
            badgeEl.classList.remove('d-none');
        } else {
            badgeEl.classList.add('d-none');
        }
    }

    function filterGames() {
        const query = storeSearch.value.toLowerCase().trim();
        // Mehrere Genres gleichzeitig moeglich -> leer heisst "alle"
        const selectedGenres = getCheckedValues(genreCheckboxes);
        // Mehrere Tags gleichzeitig moeglich -> leer heisst "alle"
        const selectedTags = getCheckedValues(tagCheckboxes);
        const minPrice = parseFloat(priceMinFilter.value);
        const maxPrice = parseFloat(priceMaxFilter.value);
        const onlySale = saleFilter.checked;

        updateActiveCountBadge(genreActiveCount, selectedGenres.length);
        updateActiveCountBadge(tagActiveCount, selectedTags.length);

        let matches = 0;
        // wie viele sichtbare Spiele pro Genre-Ueberschrift, damit leere Ueberschriften verschwinden
        const visibleCountByGenre = {};

        gameItems.forEach(item => {
            const itemTitle = item.getAttribute('data-title');
            const itemGenre = item.getAttribute('data-genre');
            const itemPrice = parseFloat(item.getAttribute('data-price'));
            const itemIsSale = item.getAttribute('data-sale') === 'true';
            const itemTags = JSON.parse(item.getAttribute('data-tags') || "[]");

            const matchTitle = itemTitle.includes(query);
            // Genre matcht, wenn keins ausgewaehlt ist ODER das Spiel in einem der ausgewaehlten Genres ist
            const matchGenre = selectedGenres.length === 0 || selectedGenres.includes(itemGenre.toLowerCase());
            // Tag matcht, wenn keins ausgewaehlt ist ODER mindestens einer der ausgewaehlten Tags dabei ist
            const matchTags = selectedTags.length === 0 || selectedTags.some(t => itemTags.includes(t));
            const matchMinPrice = isNaN(minPrice) || itemPrice >= minPrice;
            const matchMaxPrice = isNaN(maxPrice) || itemPrice <= maxPrice;
            const matchSale = !onlySale || itemIsSale;

            const isVisible = matchTitle && matchGenre && matchTags && matchMinPrice && matchMaxPrice && matchSale;

            if (isVisible) {
                item.classList.remove('d-none');
                matches++;
                visibleCountByGenre[itemGenre] = (visibleCountByGenre[itemGenre] || 0) + 1;
            } else {
                item.classList.add('d-none');
            }
        });

        // Ueberschrift ausblenden, wenn kein Spiel dieses Genres mehr sichtbar ist
        genreHeadings.forEach(heading => {
            const genre = heading.getAttribute('data-genre-heading');
            if ((visibleCountByGenre[genre] || 0) > 0) {
                heading.classList.remove('d-none');
            } else {
                heading.classList.add('d-none');
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

    if (storeSearch && priceMinFilter && priceMaxFilter && saleFilter && gameItems.length > 0) {
        storeSearch.addEventListener('input', filterGames);
        priceMinFilter.addEventListener('input', filterGames);
        priceMaxFilter.addEventListener('input', filterGames);
        saleFilter.addEventListener('change', filterGames);
        genreCheckboxes.forEach(cb => cb.addEventListener('change', filterGames));
        tagCheckboxes.forEach(cb => cb.addEventListener('change', filterGames));

        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                storeSearch.value = '';
                priceMinFilter.value = '';
                priceMaxFilter.value = '';
                saleFilter.checked = false;
                genreCheckboxes.forEach(cb => cb.checked = false);
                tagCheckboxes.forEach(cb => cb.checked = false);
                filterGames();
            });
        }

        // so we start it one time in the browser
        filterGames();
    }

    // Hover to preview video for home and store cards
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