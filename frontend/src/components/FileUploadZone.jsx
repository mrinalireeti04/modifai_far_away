import React, { useState, useRef, useCallback } from 'react'
import { Upload, X, FileText, Image, File } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

const ACCEPTED_TYPES = {
    'application/pdf': 'PDF',
    'image/png': 'PNG',
    'image/jpeg': 'JPG',
    'image/jpg': 'JPG',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'text/plain': 'TXT',
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

function getFileIcon(type) {
    if (type.startsWith('image/')) return Image
    if (type === 'application/pdf') return FileText
    return File
}

function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileUploadZone({ files, onFilesChange }) {
    const [dragActive, setDragActive] = useState(false)
    const inputRef = useRef(null)

    const handleFiles = useCallback((newFiles) => {
        const validFiles = Array.from(newFiles).filter(file => {
            if (!Object.keys(ACCEPTED_TYPES).includes(file.type)) return false
            if (file.size > MAX_FILE_SIZE) return false
            return true
        }).map(file => ({
            id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            file,
            name: file.name,
            size: file.size,
            type: file.type,
            progress: 100, // simulated
        }))

        onFilesChange([...files, ...validFiles])
    }, [files, onFilesChange])

    const handleDrag = useCallback((e) => {
        e.preventDefault()
        e.stopPropagation()
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true)
        } else if (e.type === 'dragleave') {
            setDragActive(false)
        }
    }, [])

    const handleDrop = useCallback((e) => {
        e.preventDefault()
        e.stopPropagation()
        setDragActive(false)
        if (e.dataTransfer.files?.length) {
            handleFiles(e.dataTransfer.files)
        }
    }, [handleFiles])

    const removeFile = (id) => {
        onFilesChange(files.filter(f => f.id !== id))
    }

    return (
        <div className="space-y-4">
            {/* Drop zone */}
            <div
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                className={`
                    relative flex flex-col items-center justify-center
                    rounded-xl border-2 border-dashed p-8 cursor-pointer
                    transition-all duration-200
                    ${dragActive
                        ? 'border-primary bg-primary/10 scale-[1.01]'
                        : 'border-border hover:border-primary/40 hover:bg-muted/50'
                    }
                `}
            >
                <input
                    ref={inputRef}
                    type="file"
                    multiple
                    accept={Object.keys(ACCEPTED_TYPES).join(',')}
                    className="hidden"
                    onChange={(e) => {
                        if (e.target.files?.length) handleFiles(e.target.files)
                        e.target.value = ''
                    }}
                />

                <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-3 transition-colors duration-200 ${dragActive ? 'bg-primary/20' : 'bg-muted'
                    }`}>
                    <Upload className={`w-5 h-5 transition-colors duration-200 ${dragActive ? 'text-primary' : 'text-muted-foreground'
                        }`} />
                </div>

                <p className="text-sm font-medium mb-1">
                    {dragActive ? 'Drop files here' : 'Drag & drop files here'}
                </p>
                <p className="text-xs text-muted-foreground">
                    or click to browse · PDF, PNG, JPG, DOCX, TXT · Max 50MB each
                </p>
            </div>

            {/* File list */}
            {files.length > 0 && (
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <p className="text-sm font-medium">
                            {files.length} file{files.length !== 1 ? 's' : ''} selected
                        </p>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs text-muted-foreground hover:text-destructive h-7"
                            onClick={() => onFilesChange([])}
                        >
                            Clear all
                        </Button>
                    </div>

                    <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                        {files.map((f) => {
                            const Icon = getFileIcon(f.type)
                            return (
                                <div
                                    key={f.id}
                                    className="flex items-center gap-3 rounded-lg border border-border bg-card/50 px-3 py-2 group"
                                >
                                    <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                                        <Icon className="w-4 h-4 text-primary" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-medium truncate">{f.name}</p>
                                        <p className="text-[10px] text-muted-foreground">
                                            {formatSize(f.size)} · {ACCEPTED_TYPES[f.type] || 'FILE'}
                                        </p>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                                        onClick={(e) => { e.stopPropagation(); removeFile(f.id) }}
                                    >
                                        <X className="w-3 h-3" />
                                    </Button>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}
