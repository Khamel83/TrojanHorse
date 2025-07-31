// TrojanHorse Web Interface JavaScript

let currentResults = [];
let timelineChart = null;

// Initialize the search interface
function initializeSearchInterface() {
    setupEventListeners();
    loadTimelineData();
}

// Setup event listeners
function setupEventListeners() {
    // Search form submission
    document.getElementById('searchForm').addEventListener('submit', handleSearch);
    
    // Clear button
    document.getElementById('clearBtn').addEventListener('click', clearSearch);
    
    // Export button
    document.getElementById('exportBtn').addEventListener('click', showExportModal);
    
    // Export confirmation
    document.getElementById('confirmExport').addEventListener('click', handleExport);
    
    // Timeline toggle
    document.getElementById('timelineToggle').addEventListener('click', toggleTimeline);
    
    // Timeline days selector
    document.getElementById('timelineDays').addEventListener('change', loadTimelineData);
    
    // Real-time search as user types (debounced)
    let searchTimeout;
    document.getElementById('searchQuery').addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            if (this.value.length >= 3) {
                performSearch();
            }
        }, 500);
    });
}

// Handle search form submission
function handleSearch(event) {
    event.preventDefault();
    performSearch();
}

// Perform search API call
async function performSearch() {
    const query = document.getElementById('searchQuery').value.trim();
    if (!query) return;
    
    const searchData = {
        query: query,
        type: document.getElementById('searchType').value,
        limit: 20,
        date_from: document.getElementById('dateFrom').value || null,
        date_to: document.getElementById('dateTo').value || null,
        classification: document.getElementById('classification').value || null
    };
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(searchData)
        });
        
        if (!response.ok) {
            throw new Error('Search failed');
        }
        
        const results = await response.json();
        currentResults = results.results;
        displayResults(results);
        
    } catch (error) {
        console.error('Search error:', error);
        showError('Search failed. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Display search results
function displayResults(data) {
    const resultsContainer = document.getElementById('resultsContainer');
    const resultsTitle = document.getElementById('resultsTitle');
    const resultsCount = document.getElementById('resultsCount');
    const searchResults = document.getElementById('searchResults');
    
    if (data.results.length === 0) {
        resultsContainer.style.display = 'block';
        resultsTitle.textContent = 'No Results Found';
        resultsCount.textContent = 'Try different search terms or filters';
        searchResults.innerHTML = '<div class="text-center py-5 text-muted">No transcripts match your search criteria.</div>';
        document.getElementById('exportBtn').disabled = true;
        return;
    }
    
    resultsTitle.textContent = `Search Results for "${data.query}"`;
    resultsCount.textContent = `${data.count} result${data.count !== 1 ? 's' : ''} (${data.type} search)`;
    
    searchResults.innerHTML = data.results.map(result => renderSearchResult(result)).join('');
    resultsContainer.style.display = 'block';
    document.getElementById('exportBtn').disabled = false;
}

// Render individual search result
function renderSearchResult(result) {
    const searchTypeClass = `search-type-${result.search_type}`;
    const score = result.combined_score || result.score || result.similarity || 0;
    const scoreLabel = result.combined_score ? 'Combined' : 
                     result.score ? 'Relevance' : 
                     result.similarity ? 'Similarity' : 'Score';
    
    const tags = result.tags ? result.tags.map(tag => 
        `<span class="badge bg-secondary me-1">${tag}</span>`
    ).join('') : '';
    
    const actionItems = result.action_items && result.action_items.length > 0 ? 
        `<div class="mt-2"><small class="text-muted"><strong>Action Items:</strong> ${result.action_items.length}</small></div>` : '';
    
    return `
        <div class="search-result">
            <div class="result-header">
                <div>
                    <a href="/transcript/${result.transcript_id}" class="result-title">
                        ${result.filename}
                    </a>
                    <span class="badge ${searchTypeClass} score-badge ms-2">
                        ${scoreLabel}: ${score.toFixed(3)}
                    </span>
                </div>
            </div>
            
            <div class="result-meta">
                <i class="bi bi-calendar3"></i> ${result.date}
                <i class="bi bi-clock ms-2"></i> ${result.timestamp}
                ${result.search_type === 'hybrid' ? 
                    `<span class="ms-2">
                        <small>Keyword: ${result.keyword_score.toFixed(2)} | 
                        Semantic: ${result.semantic_score.toFixed(2)}</small>
                    </span>` : ''}
            </div>
            
            <div class="result-snippet">
                ${highlightSearchTerms(result.snippet, document.getElementById('searchQuery').value)}
            </div>
            
            ${result.analysis_summary ? 
                `<div class="mt-2">
                    <small class="text-muted"><strong>Summary:</strong> ${result.analysis_summary}</small>
                </div>` : ''}
            
            ${actionItems}
            
            ${tags ? `<div class="result-tags mt-2">${tags}</div>` : ''}
        </div>
    `;
}

// Highlight search terms in text
function highlightSearchTerms(text, query) {
    if (!query || !text) return text;
    
    const terms = query.toLowerCase().split(' ').filter(term => term.length > 2);
    let highlightedText = text;
    
    terms.forEach(term => {
        const regex = new RegExp(`(${escapeRegExp(term)})`, 'gi');
        highlightedText = highlightedText.replace(regex, '<span class="highlight">$1</span>');
    });
    
    return highlightedText;
}

// Escape special regex characters
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Clear search and results
function clearSearch() {
    document.getElementById('searchForm').reset();
    document.getElementById('resultsContainer').style.display = 'none';
    document.getElementById('exportBtn').disabled = true;
    currentResults = [];
}

// Show/hide loading spinner
function showLoading(show) {
    const spinner = document.getElementById('loadingSpinner');
    const resultsContainer = document.getElementById('resultsContainer');
    
    if (show) {
        spinner.style.display = 'block';
        resultsContainer.style.display = 'none';
    } else {
        spinner.style.display = 'none';
    }
}

// Show error message
function showError(message) {
    // Create alert if it doesn't exist
    const existingAlert = document.querySelector('.alert-danger');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.querySelector('main').prepend(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Timeline functionality
function toggleTimeline() {
    const timelineCard = document.getElementById('timelineCard');
    const isVisible = timelineCard.style.display !== 'none';
    
    if (isVisible) {
        timelineCard.style.display = 'none';
    } else {
        timelineCard.style.display = 'block';
        if (!timelineChart) {
            loadTimelineData();
        }
    }
}

// Load timeline data
async function loadTimelineData() {
    const days = document.getElementById('timelineDays').value;
    
    try {
        const response = await fetch(`/api/timeline?days=${days}`);
        if (!response.ok) throw new Error('Failed to load timeline');
        
        const data = await response.json();
        renderTimelineChart(data);
        
    } catch (error) {
        console.error('Timeline error:', error);
        showError('Failed to load timeline data');
    }
}

// Render timeline chart
function renderTimelineChart(data) {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    
    if (timelineChart) {
        timelineChart.destroy();
    }
    
    const labels = data.timeline.map(item => {
        const date = new Date(item.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    const transcriptCounts = data.timeline.map(item => item.transcript_count);
    const wordCounts = data.timeline.map(item => item.total_words);
    
    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Transcripts',
                data: transcriptCounts,
                borderColor: 'rgb(13, 110, 253)',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.4,
                yAxisID: 'y'
            }, {
                label: 'Words',
                data: wordCounts,
                borderColor: 'rgb(25, 135, 84)',
                backgroundColor: 'rgba(25, 135, 84, 0.1)',
                tension: 0.4,
                yAxisID: 'y1'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Transcripts'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Words'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        }
    });
}

// Export functionality
function showExportModal() {
    if (currentResults.length === 0) {
        showError('No results to export');
        return;
    }
    
    const modal = new bootstrap.Modal(document.getElementById('exportModal'));
    modal.show();
}

// Handle export
async function handleExport() {
    const format = document.querySelector('input[name="exportFormat"]:checked').value;
    
    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                results: currentResults,
                format: format
            })
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `search_results.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('exportModal'));
        modal.hide();
        
    } catch (error) {
        console.error('Export error:', error);
        showError('Export failed. Please try again.');
    }
}

// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatTime(timeString) {
    const time = new Date(timeString);
    return time.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + K to focus search
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        document.getElementById('searchQuery').focus();
    }
    
    // Escape to clear search
    if (event.key === 'Escape') {
        clearSearch();
    }
});

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});