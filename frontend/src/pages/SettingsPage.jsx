import React, { useState } from 'react'
import {
    Save,
    SlidersHorizontal,
    Palette,
    CheckCircle2,
    Sun,
    Moon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { useTheme } from '@/components/ThemeProvider'

export default function SettingsPage() {
    const { theme, toggleTheme } = useTheme()
    const [saved, setSaved] = useState(false)



    // Defaults
    const [defaultModel, setDefaultModel] = useState('llama-3.1-8b')
    const [defaultSamples, setDefaultSamples] = useState([5])
    const [defaultThreshold, setDefaultThreshold] = useState([70])
    const [autoRetry, setAutoRetry] = useState(true)
    const [notifications, setNotifications] = useState(true)

    const handleSave = () => {
        setSaved(true)
        setTimeout(() => setSaved(false), 2500)
    }

    return (
        <div className="p-6 md:p-8 max-w-3xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Settings</h1>
                    <p className="text-sm text-muted-foreground">Configure your Modifai workspace</p>
                </div>
                <Button
                    className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground"
                    onClick={handleSave}
                >
                    {saved ? (
                        <>
                            <CheckCircle2 className="w-4 h-4" />
                            Saved!
                        </>
                    ) : (
                        <>
                            <Save className="w-4 h-4" />
                            Save Changes
                        </>
                    )}
                </Button>
            </div>


            {/* Pipeline Defaults */}
            <Card className="border-border bg-card">
                <CardHeader className="pb-4">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
                            <SlidersHorizontal className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Pipeline Defaults</CardTitle>
                            <CardDescription className="text-xs">Default configuration for new projects</CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-5">
                    <div className="space-y-2">
                        <Label className="text-xs">Default Base Model</Label>
                        <Select value={defaultModel} onValueChange={setDefaultModel}>
                            <SelectTrigger className="bg-background">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="llama-3.1-8b">Llama 3.1 8B</SelectItem>
                                <SelectItem value="mistral-7b">Mistral 7B</SelectItem>
                                <SelectItem value="gemma-2-9b">Gemma 2 9B</SelectItem>
                                <SelectItem value="phi-3-mini">Phi-3 Mini</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    <Separator />

                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <Label className="text-xs">Samples per Chunk</Label>
                            <Badge variant="secondary" className="text-xs font-mono">{defaultSamples[0]}</Badge>
                        </div>
                        <Slider value={defaultSamples} onValueChange={setDefaultSamples} min={1} max={20} step={1} />
                    </div>

                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <Label className="text-xs">Quality Threshold</Label>
                            <Badge variant="secondary" className="text-xs font-mono">{defaultThreshold[0]}%</Badge>
                        </div>
                        <Slider value={defaultThreshold} onValueChange={setDefaultThreshold} min={0} max={100} step={5} />
                    </div>

                    <Separator />

                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium">Auto-retry on failure</p>
                            <p className="text-xs text-muted-foreground">Automatically retry failed pipeline steps</p>
                        </div>
                        <Switch checked={autoRetry} onCheckedChange={setAutoRetry} />
                    </div>

                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium">Pipeline notifications</p>
                            <p className="text-xs text-muted-foreground">Get notified when pipelines complete or fail</p>
                        </div>
                        <Switch checked={notifications} onCheckedChange={setNotifications} />
                    </div>
                </CardContent>
            </Card>

            {/* Appearance */}
            <Card className="border-border bg-card">
                <CardHeader className="pb-4">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center">
                            <Palette className="w-4 h-4 text-violet-400" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Appearance</CardTitle>
                            <CardDescription className="text-xs">Customize the look and feel</CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium">Theme</p>
                            <p className="text-xs text-muted-foreground">Switch between dark and light mode</p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            className="gap-2"
                            onClick={toggleTheme}
                        >
                            {theme === 'dark' ? (
                                <>
                                    <Moon className="w-4 h-4" />
                                    Dark
                                </>
                            ) : (
                                <>
                                    <Sun className="w-4 h-4" />
                                    Light
                                </>
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
