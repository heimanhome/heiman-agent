import axios from "axios";
import { logger } from "../utils/logger.js";
import type { HeimanPluginConfig } from "../config.js";

export interface Sensor {
  did: string;
  name: string;
  type: string;
  status: string;
  value: number;
  unit: string;
  last_update: string;
}

export interface Event {
  event_id: string;
  sensor_did: string;
  level: string;
  message: string;
  acknowledged: boolean;
  timestamp: string;
}

export interface Rule {
  rule_id: string;
  name: string;
  condition: string;
  action: string;
  enabled: boolean;
  created_at: string;
}

// ============================================================
// AI/ML API 接口类型
// ============================================================

export interface MlModelInfo {
  name: string;
  type: string;
  status: string;
  accuracy: number;
  version: number;
  last_trained: string;
}

export interface MlModelDetail {
  name: string;
  type: string;
  status: string;
  accuracy: number;
  version: number;
  feature_names: string[];
  samples_trained: number;
  last_trained: string;
  params: Record<string, unknown>;
}

export interface TrainResult {
  model_name: string;
  accuracy: number;
  samples_trained: number;
  version: number;
  training_time_ms: number;
}

export interface MlHealthStatus {
  registry_ok: boolean;
  models_available: number;
  feedback_pending: number;
  retrain_needed: string[];
}

export interface AbExperiment {
  name: string;
  model_name: string;
  status: string;
  ml_ratio: number;
  samples_collected: number;
  min_sample_size: number;
  started_at: string;
}

export interface AbAnalysisResult {
  experiment_name: string;
  ml_accuracy: number;
  rule_accuracy: number;
  improvement: number;
  p_value: number;
  significant: boolean;
  confidence: number;
  recommendation: string;
  sample_count: number;
}

export interface OnlineModelStatus {
  name: string;
  feedback_count: number;
  retrain_threshold: number;
  needs_retrain: boolean;
  last_retrain: string;
  current_accuracy: number;
}

export interface FeatureImportanceItem {
  feature: string;
  importance: number;
  rank: number;
}

export interface PredictionContribution {
  feature: string;
  contribution: number;
  direction: string;
}

export interface ModelExplanation {
  model_name: string;
  model_type: string;
  n_estimators: number;
  feature_count: number;
  feature_importance: FeatureImportanceItem[];
}

export interface PredictionExplanation {
  model_name: string;
  prediction: string;
  confidence: number;
  feature_contributions: PredictionContribution[];
  base_value: number;
  explanation: string;
}

// ============================================================
// API 响应包装
// ============================================================

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

// ============================================================
// HeimanBackendClient
// ============================================================

export class HeimanBackendClient {
  private baseUrl: string;

  constructor(config: HeimanPluginConfig) {
    this.baseUrl = config.backend_url || "http://localhost:1912";
  }

  // ---- Sensor APIs ----

  async listSensors(): Promise<Sensor[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/sensors`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list sensors:", error);
      return [];
    }
  }

  async getSensor(did: string): Promise<Sensor | null> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/sensors/${did}`);
      return response.data;
    } catch (error) {
      logger.error(`Failed to get sensor ${did}:`, error);
      return null;
    }
  }

  // ---- Event APIs ----

  async listEvents(): Promise<Event[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/events`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list events:", error);
      return [];
    }
  }

  async acknowledgeEvent(eventId: string): Promise<boolean> {
    try {
      await axios.post(`${this.baseUrl}/api/events/${eventId}/acknowledge`);
      return true;
    } catch (error) {
      logger.error(`Failed to acknowledge event ${eventId}:`, error);
      return false;
    }
  }

  // ---- Rule APIs ----

  async listRules(): Promise<Rule[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/rules`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list rules:", error);
      return [];
    }
  }

  async toggleRule(ruleId: string, enabled: boolean): Promise<boolean> {
    try {
      await axios.put(`${this.baseUrl}/api/rules/${ruleId}/toggle`, { enabled });
      return true;
    } catch (error) {
      logger.error(`Failed to toggle rule ${ruleId}:`, error);
      return false;
    }
  }

  // ---- ML Model APIs ----

  async listMlModels(): Promise<ApiResponse<{ models: MlModelInfo[]; total: number }>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/ml/models`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list ML models:", error);
      return { success: false, data: { models: [], total: 0 } };
    }
  }

  async getMlModelDetail(modelName: string): Promise<ApiResponse<MlModelDetail>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/ml/models/${modelName}`);
      return response.data;
    } catch (error) {
      logger.error(`Failed to get ML model detail ${modelName}:`, error);
      return { success: false, data: {} as MlModelDetail };
    }
  }

  async trainMlModel(modelName: string, modelType?: string): Promise<ApiResponse<TrainResult>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/models/${modelName}/train`,
        { model_type: modelType || modelName }
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to train ML model ${modelName}:`, error);
      return { success: false, data: {} as TrainResult };
    }
  }

  async trainAllMlModels(): Promise<ApiResponse<{ results: TrainResult[] }>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/models/train-all`,
        {}
      );
      return response.data;
    } catch (error) {
      logger.error("Failed to train all ML models:", error);
      return { success: false, data: { results: [] } };
    }
  }

  async submitMlFeedback(
    modelName: string,
    sensorData: Record<string, unknown>,
    actualLabel: string,
    comment?: string
  ): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/models/${modelName}/feedback`,
        { sensor_data: sensorData, actual_label: actualLabel, comment }
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to submit ML feedback for ${modelName}:`, error);
      return { success: false, data: {} };
    }
  }

  async checkRetrain(modelName?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/models/check-retrain`,
        modelName ? { model_name: modelName } : {}
      );
      return response.data;
    } catch (error) {
      logger.error("Failed to check retrain:", error);
      return { success: false, data: {} };
    }
  }

  async getMlHealth(): Promise<ApiResponse<MlHealthStatus>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/ml/health`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get ML health:", error);
      return { success: false, data: {} as MlHealthStatus };
    }
  }

  // ---- A/B Testing APIs ----

  async startAbExperiment(config: {
    experiment_name: string;
    model_name: string;
    ml_ratio?: number;
    min_sample_size?: number;
    significance_level?: number;
    duration_hours?: number;
  }): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.post(`${this.baseUrl}/api/ai/ml/ab/start`, config);
      return response.data;
    } catch (error) {
      logger.error("Failed to start A/B experiment:", error);
      return { success: false, data: {} };
    }
  }

  async getAbStatus(): Promise<ApiResponse<{ experiments: AbExperiment[] }>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/ml/ab/status`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get A/B status:", error);
      return { success: false, data: { experiments: [] } };
    }
  }

  async analyzeAbExperiment(experimentName: string): Promise<ApiResponse<AbAnalysisResult>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/ab/analyze`,
        { experiment_name: experimentName }
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to analyze A/B experiment ${experimentName}:`, error);
      return { success: false, data: {} as AbAnalysisResult };
    }
  }

  async promoteAbExperiment(experimentName: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/ab/promote`,
        { experiment_name: experimentName }
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to promote A/B experiment ${experimentName}:`, error);
      return { success: false, data: {} };
    }
  }

  // ---- Online Learning APIs ----

  async getOnlineLearningStatus(): Promise<ApiResponse<{ models: OnlineModelStatus[] }>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/ml/online/status`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get online learning status:", error);
      return { success: false, data: { models: [] } };
    }
  }

  async triggerOnlineRetrain(modelName?: string): Promise<ApiResponse<{ results: TrainResult[] }>> {
    try {
      const url = modelName
        ? `${this.baseUrl}/api/ai/ml/online/retrain?model_name=${modelName}`
        : `${this.baseUrl}/api/ai/ml/online/retrain`;
      const response = await axios.post(url, {});
      return response.data;
    } catch (error) {
      logger.error("Failed to trigger online retrain:", error);
      return { success: false, data: { results: [] } };
    }
  }

  // ---- Model Explainability APIs ----

  async getFeatureImportance(modelName: string): Promise<ApiResponse<{ feature_importance: FeatureImportanceItem[] }>> {
    try {
      const response = await axios.get(
        `${this.baseUrl}/api/ai/ml/feature-importance/${modelName}`
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to get feature importance for ${modelName}:`, error);
      return { success: false, data: { feature_importance: [] } };
    }
  }

  async explainModel(modelName: string): Promise<ApiResponse<ModelExplanation>> {
    try {
      const response = await axios.get(
        `${this.baseUrl}/api/ai/ml/explain/${modelName}`
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to explain model ${modelName}:`, error);
      return { success: false, data: {} as ModelExplanation };
    }
  }

  async explainPrediction(
    modelName: string,
    features: Record<string, number>
  ): Promise<ApiResponse<PredictionExplanation>> {
    try {
      const response = await axios.post(
        `${this.baseUrl}/api/ai/ml/explain/prediction`,
        { model_name: modelName, features }
      );
      return response.data;
    } catch (error) {
      logger.error(`Failed to explain prediction for ${modelName}:`, error);
      return { success: false, data: {} as PredictionExplanation };
    }
  }

  // ---- AI Analysis APIs ----

  async getAnomalies(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/anomaly?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/anomaly`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get anomalies:", error);
      return { success: false, data: {} };
    }
  }

  async getComfort(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/comfort?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/comfort`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get comfort:", error);
      return { success: false, data: {} };
    }
  }

  async getActivity(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/activity?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/activity`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get activity:", error);
      return { success: false, data: {} };
    }
  }

  async getSuggestions(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/suggest?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/suggest`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get suggestions:", error);
      return { success: false, data: {} };
    }
  }

  async getSummary(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/summary?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/summary`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get summary:", error);
      return { success: false, data: {} };
    }
  }

  async getAiHealth(): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/health`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get AI health:", error);
      return { success: false, data: {} };
    }
  }

  // ---- Self-Learning APIs ----

  async getLearningStatus(): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/learning/status`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get learning status:", error);
      return { success: false, data: {} };
    }
  }

  async startLearning(): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.post(`${this.baseUrl}/api/ai/learning/start`, {});
      return response.data;
    } catch (error) {
      logger.error("Failed to start learning:", error);
      return { success: false, data: {} };
    }
  }

  // ---- Energy APIs ----

  async getEnergyStats(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/energy/stats?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/energy/stats`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get energy stats:", error);
      return { success: false, data: {} };
    }
  }

  async getEnergyReport(homeId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const url = homeId
        ? `${this.baseUrl}/api/ai/energy/report?home_id=${homeId}`
        : `${this.baseUrl}/api/ai/energy/report`;
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      logger.error("Failed to get energy report:", error);
      return { success: false, data: {} };
    }
  }

  // ---- Privacy APIs ----

  async getPrivacyStatus(): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/privacy/status`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get privacy status:", error);
      return { success: false, data: {} };
    }
  }

  // ---- Token APIs ----

  async getTokenUsage(): Promise<ApiResponse<Record<string, unknown>>> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/ai/token/usage`);
      return response.data;
    } catch (error) {
      logger.error("Failed to get token usage:", error);
      return { success: false, data: {} };
    }
  }
}
