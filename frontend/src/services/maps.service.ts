import api from "./api";

export type MapSearchStatus = "pending" | "running" | "done" | "failed";

export interface MapSearch {
  id: number;
  query_text: string;
  category: string | null;
  city: string | null;
  state: string | null;
  status: MapSearchStatus;
  results_count: number;
  provider: string;
  error_message: string | null;
  created_at: string;
}

export interface BusinessListing {
  id: number;
  search_query_id: number;
  place_id: string | null;
  business_name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  postcode: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  rating: number | null;
  reviews_count: number | null;
  category: string | null;
  created_at: string;
}

export interface BusinessListingList {
  items: BusinessListing[];
  total: number;
  page: number;
  per_page: number;
}

export interface MapSearchList {
  items: MapSearch[];
  total: number;
  page: number;
  per_page: number;
}

export interface ListingFilters {
  page?: number;
  per_page?: number;
  search_query_id?: number;
  category?: string;
  city?: string;
  has_email?: boolean;
  has_phone?: boolean;
  has_website?: boolean;
  min_rating?: number;
  search?: string;
}

export interface MapsPresets {
  categories: string[];
  cities: { city: string; state: string }[];
}

export interface MapsProgress {
  running: boolean;
  total: number;
  done: number;
  failed: number;
  percent: number;
  query_id: number | null;
  recently_found: Record<string, any>[];
}

const MapsService = {
  async startSearch(params: {
    query_text?: string;
    category?: string;
    city?: string;
    state?: string;
    max_results?: number;
  }) {
    const { data } = await api.post("/maps/search", params);
    return data;
  },

  async getProgress(since?: string): Promise<MapsProgress> {
    const { data } = await api.get("/maps/search-progress", { params: since ? { since } : {} });
    return data;
  },

  async listSearches(params?: { page?: number; per_page?: number }): Promise<MapSearchList> {
    const { data } = await api.get("/maps/searches", { params });
    return data;
  },

  async listListings(filters: ListingFilters = {}): Promise<BusinessListingList> {
    const params: Record<string, string | number | boolean> = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params[k] = v;
    });
    const { data } = await api.get("/maps/listings", { params });
    return data;
  },

  async getPresets(): Promise<MapsPresets> {
    const { data } = await api.get("/maps/presets");
    return data;
  },

  async exportCsv(filters: Omit<ListingFilters, "page" | "per_page"> = {}) {
    const params: Record<string, string> = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params[k] = String(v);
    });
    params.limit = "5000";
    const response = await api.get("/maps/listings/export/csv", {
      params,
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "business_listings.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

export default MapsService;
