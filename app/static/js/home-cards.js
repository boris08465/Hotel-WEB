(() => {
    const cards = Array.from(document.querySelectorAll(".home-rooms img"));
    if (!cards.length) return;

    const applyMinHeight = () => {
        cards.forEach((img) => {
            img.style.height = "auto";
        });

        const heights = cards
            .map((img) => img.getBoundingClientRect().height)
            .filter((h) => Number.isFinite(h) && h > 0);
        if (!heights.length) return;

        const minHeight = Math.min(...heights);
        cards.forEach((img) => {
            img.style.height = `${minHeight}px`;
        });
    };

    let loaded = 0;
    cards.forEach((img) => {
        if (img.complete) {
            loaded += 1;
        } else {
            img.addEventListener(
                "load",
                () => {
                    loaded += 1;
                    if (loaded === cards.length) applyMinHeight();
                },
                { once: true }
            );
        }
    });

    if (loaded === cards.length) applyMinHeight();
    window.addEventListener("resize", applyMinHeight);
})();
