/**
 * UpScrolled Video Downloader - Main Application Logic
 * Handles video download form and API communication
 */

(function() {
    'use strict';

    // Configuration
    // Set your Railway backend URL here after deployment
    const API_BASE_URL = window.location.hostname === 'localhost' 
        ? '/api' 
        : 'https://upscrolled-backend-production.up.railway.app/api';
    const UPSCROLLED_URL_PATTERN = /^https:\/\/share\.upscrolled\.com\/[a-z]{2}\/post\/[\w-]+\/?$/i;

    // DOM Elements
    const downloadForm = document.getElementById('downloadForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const downloadBtn = document.getElementById('downloadBtn');
    const progressContainer = document.getElementById('progressContainer');
    const successMessage = document.getElementById('successMessage');
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    const downloadMp4Btn = document.getElementById('downloadMp4Btn');
    const resetBtn = document.getElementById('resetBtn');
    const tryAgainBtn = document.getElementById('tryAgainBtn');

    // State
    let currentDownloadUrl = null;

    // Initialize only on pages with the download form
    if (!downloadForm) {
        initFAQ();
        initContactForm();
        return;
    }

    // Event Listeners
    videoUrlInput.addEventListener('input', handleInputChange);
    videoUrlInput.addEventListener('paste', handlePaste);
    downloadForm.addEventListener('submit', handleSubmit);
    
    if (downloadMp4Btn) {
        downloadMp4Btn.addEventListener('click', handleDownloadMp4);
    }
    
    if (resetBtn) {
        resetBtn.addEventListener('click', resetForm);
    }
    
    if (tryAgainBtn) {
        tryAgainBtn.addEventListener('click', resetForm);
    }

    /**
     * Handle input changes to enable/disable download button
     */
    function handleInputChange() {
        const url = videoUrlInput.value.trim();
        downloadBtn.disabled = !isValidUrl(url);
    }

    /**
     * Handle paste event - auto-validate after paste
     */
    function handlePaste(e) {
        setTimeout(() => {
            handleInputChange();
        }, 10);
    }

    /**
     * Validate UpScrolled URL format
     */
    function isValidUrl(url) {
        return UPSCROLLED_URL_PATTERN.test(url);
    }

    /**
     * Handle form submission
     */
    async function handleSubmit(e) {
        e.preventDefault();
        
        const url = videoUrlInput.value.trim();
        
        if (!isValidUrl(url)) {
            showError('Invalid UpScrolled link. Please check the URL format.');
            return;
        }

        // Show loading state
        showLoading();

        try {
            // Make API request
            const response = await fetch(`${API_BASE_URL}/download`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || getErrorMessage(response.status));
            }

            // Get the blob from response
            const blob = await response.blob();
            
            // Create download URL
            currentDownloadUrl = URL.createObjectURL(blob);
            
            // Show success state
            showSuccess();

        } catch (error) {
            console.error('Download error:', error);
            
            // Provide more specific error messages
            let errorMsg = 'An unexpected error occurred. Please try again.';
            
            if (error.message === 'Failed to fetch') {
                errorMsg = 'Could not connect to server. Please check your internet connection or try again later.';
                // Try health check to see if backend is reachable
                try {
                    const healthCheck = await fetch(`${API_BASE_URL.replace('/api', '')}/health`, { 
                        method: 'GET',
                        mode: 'cors'
                    });
                    if (!healthCheck.ok) {
                        errorMsg = 'Server is temporarily unavailable. Please try again later.';
                    }
                } catch (e) {
                    errorMsg = 'Server is unreachable. The backend may be down. Please try again later.';
                }
            } else {
                errorMsg = error.message;
            }
            
            showError(errorMsg);
        }
    }

    /**
     * Get user-friendly error message based on status code
     */
    function getErrorMessage(status) {
        switch (status) {
            case 400:
                return 'Invalid UpScrolled link. Please check and try again.';
            case 404:
                return 'Video not found or is private. Please check the link.';
            case 502:
                return 'Could not reach UpScrolled. Please try again later.';
            case 500:
                return 'Video processing failed. Please try again.';
            default:
                return 'An error occurred. Please try again.';
        }
    }

    /**
     * Show loading state
     */
    function showLoading() {
        downloadBtn.disabled = true;
        videoUrlInput.disabled = true;
        progressContainer.classList.add('active');
        successMessage.classList.remove('active');
        errorMessage.classList.remove('active');
    }

    /**
     * Show success state
     */
    function showSuccess() {
        progressContainer.classList.remove('active');
        successMessage.classList.add('active');
        errorMessage.classList.remove('active');
    }

    /**
     * Show error state
     */
    function showError(message) {
        progressContainer.classList.remove('active');
        successMessage.classList.remove('active');
        errorMessage.classList.add('active');
        if (errorText) {
            errorText.textContent = message;
        }
        downloadBtn.disabled = false;
        videoUrlInput.disabled = false;
    }

    /**
     * Handle MP4 download button click
     */
    function handleDownloadMp4() {
        if (!currentDownloadUrl) return;

        // Create temporary link and trigger download
        const link = document.createElement('a');
        link.href = currentDownloadUrl;
        link.download = `upscrolled-video-${Date.now()}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /**
     * Reset form to initial state
     */
    function resetForm() {
        // Clean up blob URL
        if (currentDownloadUrl) {
            URL.revokeObjectURL(currentDownloadUrl);
            currentDownloadUrl = null;
        }

        // Reset form elements
        videoUrlInput.value = '';
        videoUrlInput.disabled = false;
        downloadBtn.disabled = true;
        
        // Hide all status messages
        progressContainer.classList.remove('active');
        successMessage.classList.remove('active');
        errorMessage.classList.remove('active');

        // Focus input
        videoUrlInput.focus();
    }

    /**
     * Initialize FAQ accordion functionality
     */
    function initFAQ() {
        const faqItems = document.querySelectorAll('.faq-item');
        
        faqItems.forEach(item => {
            const question = item.querySelector('.faq-question');
            
            if (question) {
                question.addEventListener('click', function() {
                    const isActive = item.classList.contains('active');
                    
                    // Close all other items
                    faqItems.forEach(otherItem => {
                        if (otherItem !== item) {
                            otherItem.classList.remove('active');
                            const otherQuestion = otherItem.querySelector('.faq-question');
                            if (otherQuestion) {
                                otherQuestion.setAttribute('aria-expanded', 'false');
                            }
                        }
                    });
                    
                    // Toggle current item
                    item.classList.toggle('active');
                    question.setAttribute('aria-expanded', !isActive);
                });
            }
        });
    }

    /**
     * Initialize contact form functionality
     */
    function initContactForm() {
        const contactForm = document.getElementById('contactForm');
        
        if (contactForm) {
            contactForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                // Get form data
                const formData = new FormData(contactForm);
                const data = Object.fromEntries(formData.entries());
                
                // In a real implementation, this would send to an API
                // For now, show a simple confirmation
                alert('Thank you for your message! We will get back to you soon.');
                contactForm.reset();
            });
        }
    }

    // Initialize FAQ on all pages
    initFAQ();
    initContactForm();

})();
