export const PIPELINE_STEPS = [
    { id: 'upload', name: 'File Upload', icon: 'Upload', description: 'Upload files with intent description' },
    { id: 'ocr', name: 'OCR', icon: 'ScanText', description: 'Extract text from documents' },
    { id: 'chunking', name: 'Chunking', icon: 'Layers', description: 'Split text into semantic chunks' },
    { id: 'dataset_gen', name: 'Dataset Gen', icon: 'Database', description: 'Generate synthetic training samples' },
    { id: 'quality_control', name: 'Quality Control', icon: 'ShieldCheck', description: 'Score and filter samples' },
    { id: 'fine_tuning', name: 'Fine-Tuning', icon: 'Brain', description: 'Train model on clean dataset' },
    { id: 'deployment', name: 'Deployment', icon: 'Rocket', description: 'Deploy model via API' },
]

// Which steps apply to each pipeline mode
const STEPS_BY_MODE = {
    dataset_only: ['upload', 'ocr', 'chunking', 'dataset_gen', 'quality_control'],
    finetune_only: ['fine_tuning', 'deployment'],
    dataset_and_finetune: ['upload', 'ocr', 'chunking', 'dataset_gen', 'quality_control', 'fine_tuning'],
    full: ['upload', 'ocr', 'chunking', 'dataset_gen', 'quality_control', 'fine_tuning', 'deployment'],
}

export function getStepsForMode(mode) {
    const stepIds = STEPS_BY_MODE[mode] || STEPS_BY_MODE.full
    return stepIds.map(id => PIPELINE_STEPS.find(s => s.id === id)).filter(Boolean)
}

export const MOCK_PROJECTS = [
    {
        id: 'proj-001',
        name: 'Customer Support Bot',
        description: 'Fine-tuned model for automated customer support responses',
        status: 'running',
        createdAt: '2026-02-28T10:30:00Z',
        model: 'Llama 3.1 8B',
        filesCount: 12,
        currentStep: 4,
        pipeline: [
            { step: 1, status: 'complete', progress: 100 },
            { step: 2, status: 'complete', progress: 100 },
            { step: 3, status: 'complete', progress: 100 },
            { step: 4, status: 'running', progress: 62 },
            { step: 5, status: 'pending', progress: 0 },
            { step: 6, status: 'pending', progress: 0 },
            { step: 7, status: 'pending', progress: 0 },
        ],
    },
    {
        id: 'proj-002',
        name: 'Legal Document Analyzer',
        description: 'Extract and classify clauses from legal contracts',
        status: 'complete',
        createdAt: '2026-02-25T14:15:00Z',
        model: 'Mistral 7B',
        filesCount: 45,
        currentStep: 7,
        pipeline: [
            { step: 1, status: 'complete', progress: 100 },
            { step: 2, status: 'complete', progress: 100 },
            { step: 3, status: 'complete', progress: 100 },
            { step: 4, status: 'complete', progress: 100 },
            { step: 5, status: 'complete', progress: 100 },
            { step: 6, status: 'complete', progress: 100 },
            { step: 7, status: 'complete', progress: 100 },
        ],
    },
    {
        id: 'proj-003',
        name: 'Medical Report Summarizer',
        description: 'Summarize medical reports into structured data',
        status: 'error',
        createdAt: '2026-02-26T09:00:00Z',
        model: 'Gemma 2 9B',
        filesCount: 8,
        currentStep: 5,
        pipeline: [
            { step: 1, status: 'complete', progress: 100 },
            { step: 2, status: 'complete', progress: 100 },
            { step: 3, status: 'complete', progress: 100 },
            { step: 4, status: 'complete', progress: 100 },
            { step: 5, status: 'error', progress: 34 },
            { step: 6, status: 'pending', progress: 0 },
            { step: 7, status: 'pending', progress: 0 },
        ],
    },
    {
        id: 'proj-004',
        name: 'Product Description Generator',
        description: 'Generate e-commerce product descriptions from images',
        status: 'pending',
        createdAt: '2026-03-01T16:45:00Z',
        model: 'Llama 3.1 8B',
        filesCount: 30,
        currentStep: 1,
        pipeline: [
            { step: 1, status: 'running', progress: 45 },
            { step: 2, status: 'pending', progress: 0 },
            { step: 3, status: 'pending', progress: 0 },
            { step: 4, status: 'pending', progress: 0 },
            { step: 5, status: 'pending', progress: 0 },
            { step: 6, status: 'pending', progress: 0 },
            { step: 7, status: 'pending', progress: 0 },
        ],
    },
]

export const MOCK_STATS = {
    totalProjects: 4,
    modelsDeployed: 1,
    datasetsGenerated: 3,
    avgAccuracy: 94.2,
}
