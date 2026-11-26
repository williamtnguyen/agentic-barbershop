export const config = {
  businessName: import.meta.env.VITE_BUSINESS_NAME || "The Barbershop",
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, ""),
};
