import { create } from 'zustand';
import { api } from '../api/client.js';

export const useSettlementStore = create((set) => ({
  items: [],
  summary: null,
  loading: false,
  error: null,
  readyCheck: null,

  fetchSettlement: async (contractId) => {
    set({ loading: true, error: null });
    try {
      const data = await api.get(`/api/contracts/${contractId}/settlement`);
      set({
        items: data.items || [],
        summary: data.summary || null,
        readyCheck: data.ready_check || null,
        loading: false,
      });
    } catch (err) {
      set({ loading: false, error: err.message });
    }
  },
}));
