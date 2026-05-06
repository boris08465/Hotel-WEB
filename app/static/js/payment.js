const methods = document.querySelectorAll('input[name="payment_method"]');
const cardFields = document.querySelector("#card-fields");

if (methods.length && cardFields) {
    const toggleCardFields = () => {
        const selected = document.querySelector('input[name="payment_method"]:checked');
        const enabled = selected?.value === "Банковская карта";
        cardFields.querySelectorAll("input").forEach((input) => {
            input.required = enabled;
        });
    };

    methods.forEach((input) => input.addEventListener("change", toggleCardFields));
    toggleCardFields();
}
