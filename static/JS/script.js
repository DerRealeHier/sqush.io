// ---- Game-Updates Feature: Views, Votes, Follow ----
// Diese Datei NICHT einzeln einbinden, sondern den Inhalt an dein bestehendes
// script.js anhängen (ich kenne den aktuellen Inhalt von script.js nicht,
// daher kann ich dir hier nur den neuen Teil isoliert liefern).

document.addEventListener("DOMContentLoaded", function () {

    // --- View-Count pro Update, gleiches Timeout-Prinzip wie beim Game selbst ---
    document.querySelectorAll(".update-view-count").forEach(function (badge) {
        const updateId = badge.dataset.updateId;
        setTimeout(function () {
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
        }, 5000);
    });

    // --- Up-/Downvote-Buttons auf Updates ---
    document.querySelectorAll(".update-vote-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const updateId = btn.dataset.updateId;
            const voteType = btn.dataset.voteType;

            fetch(`/update/${updateId}/vote/${voteType}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.upvotes === undefined) return;

                    // beide Buttons (up & down) fuer dieses Update im DOM updaten
                    document.querySelectorAll(`.update-vote-btn[data-update-id="${updateId}"]`).forEach(function (b) {
                        const type = b.dataset.voteType;
                        const countSpan = b.querySelector(type === "up" ? ".up-count" : ".down-count");
                        if (countSpan) {
                            countSpan.textContent = type === "up" ? data.upvotes : data.downvotes;
                        }
                    });

                    // aktiven Zustand nur auf dem geklickten Button umschalten
                    document.querySelectorAll(`.update-vote-btn[data-update-id="${updateId}"]`).forEach(function (b) {
                        if (b !== btn) b.classList.remove("active");
                    });
                    btn.classList.toggle("active");
                })
                .catch(err => console.error("Update vote error:", err));
        });
    });

    // follow game
    document.querySelectorAll(".follow-game-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const gameId = btn.dataset.gameId;

            fetch(`/follow_game/${gameId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            })
                .then(res => res.json())
                .then(data => {
                    const icon = btn.querySelector("i");
                    // es kann mehrere Follow-Buttons fuer dasselbe Spiel geben (Detailseite + Updates-Feed)
                    document.querySelectorAll(`.follow-game-btn[data-game-id="${gameId}"]`).forEach(function (b) {
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

});