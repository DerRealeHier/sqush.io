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

    // ---- Filtering for the store ----
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

            const matchTitle = itemTitle.includes(query);
            const matchGenre = (genre === 'all' || itemGenre === genre);
            const matchPrice = (isNaN(maxPrice) || itemPrice <= maxPrice);
            const matchSale = (!onlySale || itemIsSale);
            const matchTag = (tagQuery === '' || itemTags.some(t => t.includes(tagQuery)));

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