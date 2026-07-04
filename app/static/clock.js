const topbarClock = document.getElementById("topbar-clock");

if (topbarClock) {
    const clockFormatter = new Intl.DateTimeFormat("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });

    function refreshTopbarClock() {
        topbarClock.textContent = clockFormatter.format(new Date());
    }

    refreshTopbarClock();
    window.setInterval(refreshTopbarClock, 1000);
}
