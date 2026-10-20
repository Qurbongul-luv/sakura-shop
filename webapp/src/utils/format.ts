export const formatPrice = (price?: number | null): string => {
  if (price === undefined || price === null) return "0 so'm";
  return `${price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")} so'm`;
};

export const calculateCargo = (weightGrams?: number | null, ratePer100g: number = 12000): number => {
  if (!weightGrams || weightGrams <= 0) return 0;
  const units = Math.ceil(weightGrams / 100);
  return units * ratePer100g;
};

export const getMediaUrl = (photo?: string | null): string => {
  if (!photo) return '/api/media/placeholder';
  if (photo.startsWith('http://') || photo.startsWith('https://')) return photo;
  return `/api/media/${photo}`;
};
