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

    //  Review vote buttons (event delegation instead of one listener per button)
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.vote-btn');
        if (!btn) return;

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

    // Wishlist Herz-Buttons (Store-Cards, Home-Cards, Detail-Seite, Wishlist-Seite)
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.wishlist-btn');
        if (!btn) return;

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

    // Cart system toggle
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".cart-btn");
        if (!btn) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const gameId = btn.getAttribute("data-game-id");
        const inCart = btn.classList.contains("active");
        const url = inCart ? `/cart/remove/${gameId}` : `/cart/add/${gameId}`;
        
        // Pass the HMAC nonce if available
        const headers = { "Content-Type": "application/json" };
        if (window.squshCartToken) {
            headers["X-Cart-Token"] = window.squshCartToken;
        }

        fetch(url, { method: "POST", headers: headers })
            .then(res => {
                if (res.status === 401 || res.redirected) {
                    window.location.href = "/login";
                    return null;
                }
                if (res.status === 400) {
                    // might be bot protection failed or game already owned
                    return res.json().then(data => { alert(data.error || "Can't do that"); return null; });
                }
                return res.json();
            })
            .then(data => {
                if (!data) return;
                
                const icon = btn.querySelector("i");
                if (data.in_cart) {
                    btn.classList.add("active");
                    icon.classList.replace("bi-cart-plus", "bi-cart-fill");
                } else {
                    btn.classList.remove("active");
                    icon.classList.replace("bi-cart-fill", "bi-cart-plus");
                    
                    // If we are on the cart page, remove the item's row
                    if (window.location.pathname === "/cart") {
                        const row = document.getElementById(`cart-item-${gameId}`);
                        if (row) row.remove();
                        // Realistically we'd recalculate the total price here, but let's just reload for simplicity
                        window.location.reload();
                    }
                }
                
                // Update all badge counts!
                document.querySelectorAll(".cart-count-badge").forEach(badge => {
                    badge.textContent = data.cart_count;
                    if (data.cart_count === 0) badge.classList.add("d-none");
                    else badge.classList.remove("d-none");
                });
            })
            .catch(err => console.error("Cart Fehler:", err));
    });

    // Cart checkout handler
    const cartCheckoutBtn = document.querySelector("#cartCheckoutBtn");
    if (cartCheckoutBtn) {
        fetch("/config")
            .then((result) => result.json())
            .then((data) => {
                const stripe = Stripe(data.publicKey);
                cartCheckoutBtn.addEventListener("click", (e) => {
                    e.preventDefault();
                    fetch("/create-cart-checkout-session")
                        .then((result) => result.json())
                        .then((data) => {
                            if (data.error) {
                                alert(data.error);
                                return;
                            }
                            return stripe.redirectToCheckout({ sessionId: data.sessionId });
                        })
                        .catch((err) => { console.error("Stripe Cart Fehler:", err); });
                });
            })
            .catch((err) => { console.error("Stripe config Fehler:", err); });
    }

    //  Stripe checkout
    // Only hit /config (and init Stripe) on pages that actually have a buy button.
    // Previously this fetch ran on every single page load, even ones without checkout.
    const submitBtn = document.querySelector("#submitBtn");
    if (submitBtn) {
        fetch("/config")
            .then((result) => result.json())
            .then((data) => {
                const stripe = Stripe(data.publicKey);

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
            })
            .catch((err) => { console.error("Stripe config Fehler:", err); });
    }

    // Sale countdown timers
    // Yea for some reason I had two timers before, and one just
    // blew away the memory and CPU usage. Should be fixed now.
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

    //Filtering for the store (multi select genres/tags + price range)
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
        // how many visible games per genre disappears when no games are visible
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

        //  dont see the title of the game if it isnt visible
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

    // Feature: Views, Votes, Follow

    // View count per Update
    const updateViewBadges = document.querySelectorAll(".update-view-count");
    if (updateViewBadges.length > 0) {
        setTimeout(() => {
            updateViewBadges.forEach(badge => {
                const updateId = badge.dataset.updateId;
                fetch(`/update_view/${updateId}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data && data.views !== undefined) {
                            badge.textContent = `${data.views} Views`;
                        }
                    })
                    .catch(err => console.error("Update view count error:", err));
            });
        }, 5000);
    }

    // up down butons on update page
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.update-vote-btn');
        if (!btn) return;

        const updateId = btn.dataset.updateId;
        const voteType = btn.dataset.voteType;

        fetch(`/update/${updateId}/vote/${voteType}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        })
            .then(res => res.json())
            .then(data => {
                if (data.upvotes === undefined) return;

                // updating both buttons
                document.querySelectorAll(`.update-vote-btn[data-update-id="${updateId}"]`).forEach(b => {
                    const type = b.dataset.voteType;
                    const countSpan = b.querySelector(type === "up" ? ".up-count" : ".down-count");
                    if (countSpan) {
                        countSpan.textContent = type === "up" ? data.upvotes : data.downvotes;
                    }
                });

                // active only one button at a time
                document.querySelectorAll(`.update-vote-btn[data-update-id="${updateId}"]`).forEach(b => {
                    if (b !== btn) b.classList.remove("active");
                });
                btn.classList.toggle("active");
            })
            .catch(err => console.error("Update vote error:", err));
    });

    // Follow Game Buttons
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.follow-game-btn');
        if (!btn) return;

        const gameId = btn.dataset.gameId;

        fetch(`/follow_game/${gameId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        })
            .then(res => res.json())
            .then(data => {
                // there can be several follow buttons on the page
                document.querySelectorAll(`.follow-game-btn[data-game-id="${gameId}"]`).forEach(b => {
                    const bIcon = b.querySelector("i");
                    if (data.following) {
                        b.classList.add("active");
                        bIcon.classList.remove("bi-bell");
                        bIcon.classList.add("bi-bell-fill");
                    } else {
                        b.classList.remove("active");
                        bIcon.classList.remove("bi-bell-fill");
                        bIcon.classList.add("bi-bell");
                    }
                });
            })
            .catch(err => console.error("Follow game error:", err));
    });

});