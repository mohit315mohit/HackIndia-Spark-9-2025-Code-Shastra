export function calculateEstimatePrice(distanceMeters, durationSeconds, rates = {}) {
    const {
        baseFare = 0,       // Flat fee
        perKmRate = 1.5,      // ₹ per km
        perMinuteRate = 0    // ₹ per minute
    } = rates;

    const distanceKm = distanceMeters / 1000;
    const durationMinutes = durationSeconds / 60;

    const price = baseFare + (distanceKm * perKmRate) + (durationMinutes * perMinuteRate);

    // Round to 2 decimals
    return Math.round(price * 100) / 100;
}