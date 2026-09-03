export const TYPE_LABEL: Record<string, string> = {
  answerable: "资料里有答案",
  unanswerable: "资料里没有，该拒绝",
  ambiguous: "问法含糊，该追问",
  gold: "正式考题",
  calibration: "校准抽样",
};

export const BEHAVE_LABEL: Record<string, string> = {
  answer: "直接回答",
  refuse: "拒绝作答",
  clarify: "先问清楚",
};

export const STATUS_LABEL: Record<string, string> = {
  PENDING: "排队中",
  RUNNING: "正在评",
  COMPLETED: "已完成",
  FAILED: "失败",
  CANCELLED: "已取消",
  not_calibrated: "尚未校准",
  insufficient: "样本不够",
  calibrated: "已校准",
};

export const CAUSE_LABEL: Record<string, string> = {
  评测集: "题目本身有问题",
  检索漏召回: "没找到该找的资料",
  检索噪声: "找到了，但掺了太多无关内容",
  生成幻觉: "资料在，答案却编了资料里没有的话",
  生成答差: "资料在，但答偏了或答不全",
  行为错误: "该拒的乱答，或该问清楚却直接答了",
};

export const RV_LABEL: Record<string, string> = {
  kb: "知识库版本",
  chunk: "切分方式",
  embedding: "向量模型",
  retrieval: "检索策略",
  rerank: "重排序",
  generator: "回答模型",
  prompt: "提示词",
};

export function pct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(0)}%`;
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}
