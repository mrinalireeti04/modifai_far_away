import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    FolderKanban,
    Rocket,
    Database,
    TrendingUp,
    Plus,
    ArrowRight,
    Sparkles,
    Upload,
    ScanText,
    Layers,
    Brain,
    ShieldCheck,
    Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import StatsCard from '@/components/StatsCard'
import ProjectCard from '@/components/ProjectCard'
import { PIPELINE_STEPS } from '@/data/mockData'
import { apiClient } from '@/api/client'

const pipelineIcons = [Upload, ScanText, Layers, Database, ShieldCheck, Brain, Rocket]

export default function DashboardPage() {
    const navigate = useNavigate()
    const [projects, setProjects] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchProjects = async () => {
            try {
                const data = await apiClient.get('projects/')
                const mapped = data.map(p => ({
                    id: p.id,
                    name: p.name,
                    description: p.description || '',
                    status: p.status,
                    createdAt: p.created_at,
                    model: p.base_model || 'Unknown',
                    mode: p.mode,
                    filesCount: 0,
                    currentStep: 0,
                    pipeline: [],
                }))
                setProjects(mapped)
            } catch (err) {
                console.error('Failed to fetch projects for dashboard:', err)
            } finally {
                setLoading(false)
            }
        }
        fetchProjects()
    }, [])

    // Derive stats from real data
    const stats = {
        totalProjects: projects.length,
        modelsDeployed: projects.filter(p => p.mode === 'full' && p.status === 'completed').length,
        datasetsGenerated: projects.filter(p => p.status === 'completed').length,
        running: projects.filter(p => p.status === 'running').length,
    }

    const recentProjects = projects.slice(0, 4)

    return (
        <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto">
            {/* ── Hero Section ── */}
            <section className="relative rounded-2xl overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-primary/5 to-transparent" />
                <div className="absolute top-0 right-0 w-96 h-96 bg-primary/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />

                <div className="relative px-8 py-12 md:py-16">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                        <div className="space-y-4 max-w-xl">
                            <div className="flex items-center gap-2">
                                <Sparkles className="w-5 h-5 text-primary" />
                                <span className="text-sm font-medium text-primary">AI Model Factory</span>
                            </div>
                            <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
                                Transform Your Data Into{' '}
                                <span className="gradient-text">Fine-Tuned Models</span>
                            </h1>
                            <p className="text-muted-foreground leading-relaxed">
                                Upload documents, generate synthetic datasets, and deploy custom AI models — all from one pipeline.
                            </p>
                            <div className="flex items-center gap-3 pt-2">
                                <Button
                                    size="lg"
                                    className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground glow"
                                    onClick={() => navigate('/projects/new')}
                                >
                                    <Plus className="w-4 h-4" />
                                    New Project
                                </Button>
                                <Button
                                    variant="outline"
                                    size="lg"
                                    className="gap-2"
                                    onClick={() => navigate('/projects')}
                                >
                                    View Projects
                                    <ArrowRight className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>

                        {/* Mini pipeline visualization */}
                        <div className="hidden lg:flex items-center gap-1">
                            {PIPELINE_STEPS.map((step, i) => {
                                const Icon = pipelineIcons[i]
                                return (
                                    <div key={step.id} className="flex items-center">
                                        <div className="flex flex-col items-center gap-1.5 group">
                                            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center transition-all duration-200 group-hover:bg-primary/20 group-hover:scale-110">
                                                <Icon className="w-4 h-4 text-primary" />
                                            </div>
                                            <span className="text-[10px] text-muted-foreground text-center w-14 leading-tight">
                                                {step.name}
                                            </span>
                                        </div>
                                        {i < PIPELINE_STEPS.length - 1 && (
                                            <div className="w-4 h-px bg-border mx-0.5 mb-5" />
                                        )}
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Stats Grid ── */}
            <section>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatsCard
                        icon={FolderKanban}
                        label="Total Projects"
                        value={stats.totalProjects}
                    />
                    <StatsCard
                        icon={Rocket}
                        label="Models Deployed"
                        value={stats.modelsDeployed}
                    />
                    <StatsCard
                        icon={Database}
                        label="Datasets Generated"
                        value={stats.datasetsGenerated}
                    />
                    <StatsCard
                        icon={TrendingUp}
                        label="Running"
                        value={stats.running}
                    />
                </div>
            </section>

            {/* ── Recent Projects ── */}
            <section>
                <div className="flex items-center justify-between mb-5">
                    <div>
                        <h2 className="text-lg font-semibold">Recent Projects</h2>
                        <p className="text-sm text-muted-foreground">Your latest model training pipelines</p>
                    </div>
                    <Button
                        variant="ghost"
                        className="gap-1 text-sm text-muted-foreground hover:text-foreground"
                        onClick={() => navigate('/projects')}
                    >
                        View all
                        <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                </div>
                {loading ? (
                    <div className="flex justify-center py-12">
                        <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                ) : recentProjects.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                        <p className="text-sm">No projects yet. Create your first one!</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {recentProjects.map(project => (
                            <ProjectCard key={project.id} project={project} />
                        ))}
                    </div>
                )}
            </section>

            {/* ── Quick Start CTA ── */}
            <section>
                <Card className="border-dashed border-2 border-primary/20 bg-primary/5 hover:bg-primary/8 transition-colors cursor-pointer"
                    onClick={() => navigate('/projects/new')}
                >
                    <CardContent className="flex flex-col items-center justify-center py-10 gap-3">
                        <div className="w-12 h-12 rounded-full bg-primary/15 flex items-center justify-center">
                            <Plus className="w-6 h-6 text-primary" />
                        </div>
                        <div className="text-center">
                            <h3 className="font-semibold">Start a New Project</h3>
                            <p className="text-sm text-muted-foreground mt-1">
                                Upload your documents and create a fine-tuned AI model in minutes
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </section>
        </div>
    )
}
