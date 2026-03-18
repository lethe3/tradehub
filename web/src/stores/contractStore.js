import { create } from 'zustand';
import { api } from '../api/client.js';

export const useContractStore = create((set, get) => ({
  contracts: [],
  loading: false,
  error: null,

  fetchContracts: async () => {
    set({ loading: true, error: null });
    try {
      const data = await api.get('/api/contracts');
      set({ contracts: data || [], loading: false });
    } catch (err) {
      set({ loading: false, error: err.message });
    }
  },

  createContract: async (formData) => {
    const data = await api.post('/api/contracts', formData);
    set((state) => ({ contracts: [data, ...state.contracts] }));
    return data;
  },

  // Current contract detail
  currentContract: null,
  weigh_tickets: [],
  assay_reports: [],
  recipe: null,
  detailLoading: false,
  detailError: null,

  fetchContractDetail: async (id) => {
    set({ detailLoading: true, detailError: null, currentContract: null, weigh_tickets: [], assay_reports: [], recipe: null });
    try {
      const [contract, tickets, reports] = await Promise.all([
        api.get(`/api/contracts/${id}`),
        api.get(`/api/contracts/${id}/weigh-tickets`),
        api.get(`/api/contracts/${id}/assay-reports`),
      ]);

      let recipe = null;
      try {
        recipe = await api.get(`/api/contracts/${id}/recipe`);
      } catch {
        // recipe may not exist yet — that's fine
      }

      set({
        currentContract: contract,
        weigh_tickets: tickets || [],
        assay_reports: reports || [],
        recipe,
        detailLoading: false,
      });
    } catch (err) {
      set({ detailLoading: false, detailError: err.message });
    }
  },

  addWeighTicket: async (contractId, data) => {
    const ticket = await api.post(`/api/contracts/${contractId}/weigh-tickets`, data);
    set((state) => ({ weigh_tickets: [...state.weigh_tickets, ticket] }));
    return ticket;
  },

  deleteWeighTicket: async (contractId, ticketId) => {
    await api.del(`/api/contracts/${contractId}/weigh-tickets/${ticketId}`);
    set((state) => ({
      weigh_tickets: state.weigh_tickets.filter((t) => t.id !== ticketId),
    }));
  },

  addAssayReport: async (contractId, data) => {
    const report = await api.post(`/api/contracts/${contractId}/assay-reports`, data);
    set((state) => ({ assay_reports: [...state.assay_reports, report] }));
    return report;
  },

  deleteAssayReport: async (contractId, reportId) => {
    await api.del(`/api/contracts/${contractId}/assay-reports/${reportId}`);
    set((state) => ({
      assay_reports: state.assay_reports.filter((r) => r.id !== reportId),
    }));
  },

  saveRecipe: async (contractId, recipe) => {
    const saved = await api.put(`/api/contracts/${contractId}/recipe`, recipe);
    set({ recipe: saved });
    return saved;
  },
}));
