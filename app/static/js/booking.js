const form = document.querySelector("#booking-form");

if (form) {
    const checkIn = document.querySelector("#check_in");
    const checkOut = document.querySelector("#check_out");
    const children = document.querySelector("#children");
    const daysNode = document.querySelector("#days");
    const priceNode = document.querySelector("#price");

    const selectedRoom = () => document.querySelector('input[name="room_type"]:checked');

    const updateSummary = () => {
        const start = checkIn.value ? new Date(checkIn.value) : null;
        const end = checkOut.value ? new Date(checkOut.value) : null;
        let days = 0;
        if (start && end) {
            days = Math.floor((end - start) / 86400000);
            if (days < 0) days = 0;
        }
        const basePrice = Number(selectedRoom()?.dataset.price || 0);
        const childCount = Math.max(0, Number(children.value || 0));
        const price = days > 0 ? basePrice * days + childCount * 500 * days : 0;
        daysNode.textContent = days;
        priceNode.textContent = price.toLocaleString("ru-RU") + " рублей";
    };

    form.addEventListener("input", updateSummary);
    form.addEventListener("change", updateSummary);
    updateSummary();
}
