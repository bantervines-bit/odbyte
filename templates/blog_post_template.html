{% extends "base.html" %}

{% block title %}{{ post.title }} - ODByte Blog{% endblock %}

{% block extra_css %}
<style>
    /* Blog Container */
    .blog-content {
        max-width: 100%;
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
    }
    
    /* Heading Styles - Proper Hierarchy */
    .blog-content h1 {
        font-size: 2.5rem;
        font-weight: 800;
        margin-top: 3rem;
        margin-bottom: 1.5rem;
        color: #60a5fa;
        line-height: 1.2;
        letter-spacing: -0.025em;
    }
    
    .blog-content h2 {
        font-size: 2rem;
        font-weight: 700;
        margin-top: 3rem;
        margin-bottom: 1.5rem;
        color: #60a5fa;
        line-height: 1.3;
        letter-spacing: -0.02em;
    }
    
    .blog-content h3 {
        font-size: 1.5rem;
        font-weight: 600;
        margin-top: 2.5rem;
        margin-bottom: 1.25rem;
        color: #93c5fd;
        line-height: 1.4;
    }
    
    .blog-content h4 {
        font-size: 1.25rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 1rem;
        color: #a78bfa;
        line-height: 1.5;
    }
    
    .blog-content h5 {
        font-size: 1.125rem;
        font-weight: 600;
        margin-top: 1.75rem;
        margin-bottom: 0.875rem;
        color: #c4b5fd;
        line-height: 1.5;
    }
    
    .blog-content h6 {
        font-size: 1rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        color: #ddd6fe;
        line-height: 1.5;
    }
    
    /* Paragraph and Text Styles */
    .blog-content p {
        color: #d1d5db;
        margin-bottom: 1.75rem;
        line-height: 1.875;
        font-size: 1.0625rem;
    }
    
    .blog-content ul, .blog-content ol {
        color: #d1d5db;
        margin-bottom: 1.75rem;
        margin-top: 1rem;
        padding-left: 2rem;
        line-height: 1.875;
    }
    
    .blog-content li {
        margin-bottom: 0.75rem;
        line-height: 1.875;
    }
    
    .blog-content strong {
        color: #fff;
        font-weight: 600;
    }
    
    /* Inline code */
    .blog-content p code,
    .blog-content li code {
        background: #1a1a1a;
        padding: 0.2rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.9em;
        color: #60a5fa;
        font-family: 'Courier New', monospace;
    }
    
    /* BOXED PROMPT CARD - Main Style */
    .prompt-box {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
        border: 2px solid #6366f1;
        border-radius: 1rem;
        padding: 0;
        margin: 2.5rem 0;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.2);
        transition: all 0.3s ease;
    }
    
    .prompt-box:hover {
        box-shadow: 0 12px 32px rgba(99, 102, 241, 0.3);
        transform: translateY(-2px);
    }
    
    .prompt-header {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        padding: 1.25rem 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
        border-bottom: 2px solid #6366f1;
    }
    
    .prompt-label {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-weight: 700;
        font-size: 1rem;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .prompt-label-icon {
        font-size: 1.5rem;
    }
    
    .copy-prompt-btn {
        padding: 0.625rem 1.25rem;
        background: #ffffff;
        color: #4f46e5;
        border: none;
        border-radius: 0.5rem;
        font-size: 0.9375rem;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    
    .copy-prompt-btn:hover {
        background: #f3f4f6;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .copy-prompt-btn:active {
        transform: translateY(0);
    }
    
    .copy-prompt-btn.copied {
        background: #10b981;
        color: white;
    }
    
    .prompt-body {
        padding: 2rem;
        background: rgba(15, 23, 42, 0.5);
    }
    
    .prompt-content {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 0.75rem;
        padding: 1.5rem;
        color: #e2e8f0;
        font-family: 'Courier New', Consolas, monospace;
        font-size: 1rem;
        line-height: 1.8;
        white-space: pre-wrap;
        word-break: break-word;
        overflow-wrap: break-word;
        max-width: 100%;
        overflow-x: auto;
        box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    
    .why-it-works {
        margin-top: 1.5rem;
        padding: 1.25rem 1.5rem;
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        border-left: 4px solid #60a5fa;
        border-radius: 0.75rem;
        color: #dbeafe;
        font-size: 1rem;
        line-height: 1.75;
    }
    
    .why-it-works-title {
        color: #60a5fa;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        font-size: 1.0625rem;
    }
    
    /* Regular code blocks (non-prompts) */
    .blog-content pre {
        background: #0b0b0b;
        border: 1px solid #374151;
        border-radius: 0.75rem;
        padding: 1.5rem;
        margin: 2rem 0;
        overflow-x: auto;
        position: relative;
        max-width: 100%;
    }
    
    .blog-content pre code {
        background: none;
        padding: 0;
        color: #e5e7eb;
        font-size: 0.9375rem;
        line-height: 1.8;
        display: block;
        white-space: pre;
        word-break: normal;
        overflow-wrap: normal;
    }
    
    /* Links */
    .blog-content a {
        color: #60a5fa;
        text-decoration: underline;
        word-break: break-word;
        transition: color 0.2s;
    }
    
    .blog-content a:hover {
        color: #93c5fd;
    }
    
    /* Blockquotes */
    .blog-content blockquote {
        border-left: 4px solid #60a5fa;
        padding-left: 1.5rem;
        margin: 2rem 0;
        color: #9ca3af;
        font-style: italic;
        line-height: 1.875;
        font-size: 1.0625rem;
    }
    
    /* Code block wrapper for regular code */
    .code-block-wrapper {
        position: relative;
        margin: 2rem 0;
        max-width: 100%;
        overflow: hidden;
    }
    
    .code-block-wrapper pre {
        margin: 0;
        padding-top: 3.5rem;
    }
    
    /* Copy button for regular code blocks */
    .copy-code-btn {
        position: absolute;
        top: 0.75rem;
        right: 0.75rem;
        padding: 0.5rem 1rem;
        background: #6366f1;
        color: white;
        border: none;
        border-radius: 0.5rem;
        font-size: 0.8125rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        z-index: 10;
        display: flex;
        align-items: center;
        gap: 0.375rem;
    }
    
    .copy-code-btn:hover {
        background: #4f46e5;
        transform: translateY(-1px);
    }
    
    .copy-code-btn.copied {
        background: #10b981;
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .blog-content h1 {
            font-size: 2rem;
            margin-top: 2rem;
        }
        
        .blog-content h2 {
            font-size: 1.75rem;
            margin-top: 2rem;
        }
        
        .blog-content h3 {
            font-size: 1.375rem;
            margin-top: 1.75rem;
        }
        
        .blog-content h4 {
            font-size: 1.125rem;
            margin-top: 1.5rem;
        }
        
        .blog-content p,
        .blog-content ul,
        .blog-content ol {
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .prompt-box {
            margin: 2rem 0;
        }
        
        .prompt-header {
            padding: 1rem;
            flex-direction: column;
            align-items: flex-start;
        }
        
        .prompt-body {
            padding: 1.25rem;
        }
        
        .prompt-content {
            padding: 1.25rem;
            font-size: 0.9375rem;
        }
        
        .copy-prompt-btn {
            width: 100%;
            justify-content: center;
        }
        
        .blog-content pre {
            padding: 1rem;
            font-size: 0.875rem;
        }
        
        .code-block-wrapper pre {
            padding-top: 3rem;
        }
    }
    
    /* Prevent horizontal scroll */
    .blog-content * {
        max-width: 100%;
    }
</style>
{% endblock %}

{% block content %}
<article class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <header class="mb-10">
        <div class="flex items-center gap-3 mb-6 flex-wrap">
            <span class="px-4 py-1.5 bg-blue-600 text-white text-sm font-semibold rounded-lg">
                {{ post.category }}
            </span>
            <span class="text-gray-400 text-sm">{{ post.date }}</span>
            <span class="text-gray-500">•</span>
            <span class="text-gray-400 text-sm">By {{ post.author }}</span>
        </div>
        
        <h1 class="text-4xl md:text-5xl font-bold mb-6 leading-tight bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            {{ post.title }}
        </h1>
        
        {% if post.excerpt %}
        <p class="text-xl text-gray-300 leading-relaxed">
            {{ post.excerpt }}
        </p>
        {% endif %}
    </header>
    
    <div class="blog-content prose prose-invert max-w-none" id="blog-content">
        {{ post.content|safe }}
    </div>
    
    <!-- Call to Action -->
    <div class="text-center my-16 bg-gradient-to-br from-blue-900/40 to-purple-900/40 border-2 border-blue-500/50 rounded-2xl p-10 shadow-2xl">
        <div class="text-5xl mb-4">💡</div>
        <h3 class="text-3xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            Save Your Favorite Prompts
        </h3>
        <p class="text-lg text-gray-300 mb-8 max-w-2xl mx-auto">
            Join ODByte to organize, share, and discover the best AI prompts for your workflow
        </p>
        <a href="{{ url_for('signup') }}" 
           class="inline-block px-10 py-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl text-lg font-bold hover:opacity-90 transition transform hover:scale-105 shadow-lg">
            🚀 Get Started Free
        </a>
    </div>
    
    <!-- Navigation -->
    <div class="flex justify-between items-center mt-12 pt-8 border-t-2 border-gray-800 flex-wrap gap-4">
        <a href="{{ url_for('blog') }}" 
           class="px-8 py-3 bg-gray-800 hover:bg-gray-700 rounded-lg transition font-semibold flex items-center gap-2">
            ← Back to Blog
        </a>
        
        <a href="{{ url_for('explore') }}" 
           class="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition font-semibold flex items-center gap-2">
            Explore Prompts →
        </a>
    </div>
</article>
{% endblock %}

{% block extra_js %}
<script>
document.addEventListener('DOMContentLoaded', function() {
    const blogContent = document.getElementById('blog-content');
    let promptCounter = 0;
    
    // Find all paragraphs with "Prompt:" or strong tags with "Prompt:"
    const allElements = blogContent.querySelectorAll('p, strong');
    
    allElements.forEach((element) => {
        const text = element.textContent.trim();
        
        // Check if this is a prompt indicator
        if (text.startsWith('Prompt:') || (element.tagName === 'STRONG' && text === 'Prompt:')) {
            promptCounter++;
            
            // Find the actual prompt content (next element)
            let promptElement = element.nextElementSibling;
            if (element.tagName === 'STRONG') {
                promptElement = element.parentElement.nextElementSibling;
            }
            
            if (!promptElement) return;
            
            // Get prompt text
            let promptText = promptElement.textContent.trim();
            
            // Find "Why it works" section
            let whyElement = promptElement.nextElementSibling;
            let whyText = '';
            
            if (whyElement && whyElement.textContent.includes('Why it works:')) {
                whyText = whyElement.textContent.replace(/\*\*Why it works:\*\*/gi, '')
                                                .replace(/Why it works:/gi, '')
                                                .trim();
            }
            
            // Create prompt box
            const promptBox = document.createElement('div');
            promptBox.className = 'prompt-box';
            promptBox.innerHTML = `
                <div class="prompt-header">
                    <div class="prompt-label">
                        <span class="prompt-label-icon">💬</span>
                        <span>Prompt ${promptCounter}</span>
                    </div>
                    <button class="copy-prompt-btn" data-prompt="${promptCounter}">
                        <span class="copy-icon">📋</span>
                        <span class="copy-text">Copy Prompt</span>
                    </button>
                </div>
                <div class="prompt-body">
                    <div class="prompt-content">${promptText}</div>
                    ${whyText ? `
                        <div class="why-it-works">
                            <div class="why-it-works-title">
                                <span>💡</span>
                                <span>Why it works:</span>
                            </div>
                            <div>${whyText}</div>
                        </div>
                    ` : ''}
                </div>
            `;
            
            // Replace elements with prompt box
            if (element.tagName === 'STRONG') {
                element.parentElement.parentNode.insertBefore(promptBox, element.parentElement);
                element.parentElement.remove();
            } else {
                element.parentNode.insertBefore(promptBox, element);
                element.remove();
            }
            
            promptElement.remove();
            if (whyElement && whyElement.textContent.includes('Why it works:')) {
                whyElement.remove();
            }
            
            // Add copy functionality
            const copyBtn = promptBox.querySelector('.copy-prompt-btn');
            const promptContent = promptBox.querySelector('.prompt-content');
            
            copyBtn.addEventListener('click', function() {
                const textToCopy = promptContent.textContent.trim();
                
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const icon = copyBtn.querySelector('.copy-icon');
                    const text = copyBtn.querySelector('.copy-text');
                    
                    icon.textContent = '✅';
                    text.textContent = 'Copied!';
                    copyBtn.classList.add('copied');
                    
                    setTimeout(() => {
                        icon.textContent = '📋';
                        text.textContent = 'Copy Prompt';
                        copyBtn.classList.remove('copied');
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy:', err);
                    alert('Failed to copy prompt');
                });
            });
        }
    });
    
    // Add copy buttons to regular code blocks
    const codeBlocks = blogContent.querySelectorAll('pre');
    
    codeBlocks.forEach((block) => {
        // Skip if already in prompt box
        if (block.closest('.prompt-box')) return;
        
        // Skip if already wrapped
        if (block.parentElement.classList.contains('code-block-wrapper')) return;
        
        // Wrap in div
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        block.parentNode.insertBefore(wrapper, block);
        wrapper.appendChild(block);
        
        // Add copy button
        const button = document.createElement('button');
        button.className = 'copy-code-btn';
        button.innerHTML = '<span class="icon">📋</span> <span class="text">Copy</span>';
        
        button.addEventListener('click', function() {
            const code = block.querySelector('code');
            const text = code ? code.textContent : block.textContent;
            
            navigator.clipboard.writeText(text).then(() => {
                const icon = button.querySelector('.icon');
                const text = button.querySelector('.text');
                
                icon.textContent = '✅';
                text.textContent = 'Copied!';
                button.classList.add('copied');
                
                setTimeout(() => {
                    icon.textContent = '📋';
                    text.textContent = 'Copy';
                    button.classList.remove('copied');
                }, 2000);
            });
        });
        
        wrapper.appendChild(button);
    });
});
</script>
{% endblock %}
