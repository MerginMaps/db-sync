/**
 * Wizard navigation and form handling logic
 */

document.addEventListener('DOMContentLoaded', function() {
    // State
    let currentStep = 1;
    const totalSteps = 6;
    let merginValidated = false;
    let postgresValidated = false;

    // Elements
    const steps = document.querySelectorAll('.wizard-step');
    const progressSteps = document.querySelectorAll('.progress-step');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    // Mergin elements
    const merginUrl = document.getElementById('mergin-url');
    const merginUsername = document.getElementById('mergin-username');
    const merginPassword = document.getElementById('mergin-password');
    const testMerginBtn = document.getElementById('test-mergin-btn');
    const merginStatus = document.getElementById('mergin-status');

    // PostgreSQL elements
    const pgConnInfo = document.getElementById('pg-conn-info');
    const testPostgresBtn = document.getElementById('test-postgres-btn');
    const postgresStatus = document.getElementById('postgres-status');
    const postgresInfo = document.getElementById('postgres-info');

    // Project elements
    const merginProject = document.getElementById('mergin-project');
    const refreshProjectsBtn = document.getElementById('refresh-projects-btn');
    const projectsStatus = document.getElementById('projects-status');

    // GeoPackage elements
    const syncFile = document.getElementById('sync-file');
    const gpkgStatus = document.getElementById('gpkg-status');

    // Schema elements
    const schemaModified = document.getElementById('schema-modified');
    const schemaBase = document.getElementById('schema-base');

    // Save config elements
    const saveConfigBtn = document.getElementById('save-config-btn');
    const saveStatus = document.getElementById('save-status');
    const configSummary = document.getElementById('config-summary');

    // Navigation
    function showStep(stepNum) {
        steps.forEach((step, i) => {
            step.classList.toggle('active', i + 1 === stepNum);
        });

        progressSteps.forEach((step, i) => {
            step.classList.remove('active', 'completed');
            if (i + 1 === stepNum) {
                step.classList.add('active');
            } else if (i + 1 < stepNum) {
                step.classList.add('completed');
            }
        });

        prevBtn.disabled = stepNum === 1;
        nextBtn.textContent = stepNum === totalSteps ? 'Finish' : 'Next';

        currentStep = stepNum;

        // Auto-load data for certain steps
        if (stepNum === 3 && merginValidated) {
            loadProjects();
        }
        if (stepNum === 6) {
            updateConfigSummary();
        }
    }

    function validateCurrentStep() {
        switch (currentStep) {
            case 1:
                if (!merginValidated) {
                    showStatus(merginStatus, 'error', 'Please test your Mergin credentials first');
                    return false;
                }
                return true;
            case 2:
                if (!postgresValidated) {
                    showStatus(postgresStatus, 'error', 'Please test your PostgreSQL connection first');
                    return false;
                }
                return true;
            case 3:
                if (!merginProject.value) {
                    showStatus(projectsStatus, 'error', 'Please select a project');
                    return false;
                }
                loadGpkgFiles();
                return true;
            case 4:
                if (!syncFile.value) {
                    showStatus(gpkgStatus, 'error', 'Please select a GeoPackage file');
                    return false;
                }
                // Set default schema names based on project
                if (!schemaModified.value) {
                    const projectName = merginProject.value.split('/').pop().replace(/[^a-z0-9]/gi, '_').toLowerCase();
                    schemaModified.value = projectName + '_data';
                    schemaBase.value = projectName + '_data_base';
                }
                return true;
            case 5:
                if (!schemaModified.value || !schemaBase.value) {
                    showStatus(document.getElementById('schema-status'), 'error', 'Please enter both schema names');
                    return false;
                }
                return true;
            default:
                return true;
        }
    }

    prevBtn.addEventListener('click', function() {
        if (currentStep > 1) {
            showStep(currentStep - 1);
        }
    });

    nextBtn.addEventListener('click', function() {
        if (currentStep === totalSteps) {
            // Finish button - redirect to dashboard
            window.location.href = '/dashboard';
        } else if (validateCurrentStep()) {
            showStep(currentStep + 1);
        }
    });

    // Test Mergin Connection
    testMerginBtn.addEventListener('click', async function() {
        setLoading(testMerginBtn, true);
        hideStatus(merginStatus);

        try {
            const response = await fetch('/api/wizard/validate-mergin', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    url: merginUrl.value,
                    username: merginUsername.value,
                    password: merginPassword.value
                })
            });
            const data = await response.json();

            if (data.success) {
                showStatus(merginStatus, 'success', data.message);
                merginValidated = true;
            } else {
                showStatus(merginStatus, 'error', data.error);
                merginValidated = false;
            }
        } catch (error) {
            showStatus(merginStatus, 'error', 'Network error: ' + error.message);
            merginValidated = false;
        } finally {
            setLoading(testMerginBtn, false);
        }
    });

    // Reset validation when credentials change
    [merginUrl, merginUsername, merginPassword].forEach(el => {
        el.addEventListener('input', function() {
            merginValidated = false;
            hideStatus(merginStatus);
        });
    });

    // Test PostgreSQL Connection
    testPostgresBtn.addEventListener('click', async function() {
        setLoading(testPostgresBtn, true);
        hideStatus(postgresStatus);
        postgresInfo.style.display = 'none';

        try {
            const response = await fetch('/api/wizard/test-postgres', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    conn_info: pgConnInfo.value
                })
            });
            const data = await response.json();

            if (data.success) {
                showStatus(postgresStatus, 'success', 'Connected to database: ' + data.database);
                postgresValidated = true;

                // Show database info
                let info = `<p><strong>PostgreSQL:</strong> ${data.pg_version.split(',')[0]}</p>`;
                info += `<p><strong>PostGIS:</strong> ${data.has_postgis ? 'v' + data.postgis_version : 'Not installed'}</p>`;
                if (data.schemas.length > 0) {
                    info += `<p><strong>Existing schemas:</strong> ${data.schemas.join(', ')}</p>`;
                }
                postgresInfo.innerHTML = info;
                postgresInfo.style.display = 'block';

                if (!data.has_postgis) {
                    showStatus(postgresStatus, 'info', 'Warning: PostGIS extension is not installed. Some features may not work.');
                }
            } else {
                showStatus(postgresStatus, 'error', data.error);
                postgresValidated = false;
            }
        } catch (error) {
            showStatus(postgresStatus, 'error', 'Network error: ' + error.message);
            postgresValidated = false;
        } finally {
            setLoading(testPostgresBtn, false);
        }
    });

    pgConnInfo.addEventListener('input', function() {
        postgresValidated = false;
        hideStatus(postgresStatus);
        postgresInfo.style.display = 'none';
    });

    // Load Projects
    async function loadProjects() {
        merginProject.innerHTML = '<option value="">Loading projects...</option>';
        hideStatus(projectsStatus);

        try {
            const response = await fetch('/api/wizard/list-projects', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    url: merginUrl.value,
                    username: merginUsername.value,
                    password: merginPassword.value
                })
            });
            const data = await response.json();

            if (data.success) {
                merginProject.innerHTML = '<option value="">Select a project...</option>';
                data.projects.forEach(project => {
                    const option = document.createElement('option');
                    option.value = project.full_name;
                    option.textContent = `${project.full_name} (${project.version})`;
                    merginProject.appendChild(option);
                });
                if (data.projects.length === 0) {
                    showStatus(projectsStatus, 'info', 'No projects found. Create a project in Mergin Maps first.');
                }
            } else {
                showStatus(projectsStatus, 'error', data.error);
                merginProject.innerHTML = '<option value="">Error loading projects</option>';
            }
        } catch (error) {
            showStatus(projectsStatus, 'error', 'Network error: ' + error.message);
            merginProject.innerHTML = '<option value="">Error loading projects</option>';
        }
    }

    refreshProjectsBtn.addEventListener('click', loadProjects);

    // Load GeoPackage files when project changes
    merginProject.addEventListener('change', loadGpkgFiles);

    async function loadGpkgFiles() {
        if (!merginProject.value) {
            syncFile.innerHTML = '<option value="">Select a project first</option>';
            return;
        }

        syncFile.innerHTML = '<option value="">Loading files...</option>';
        hideStatus(gpkgStatus);

        try {
            const response = await fetch('/api/wizard/project-files', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    url: merginUrl.value,
                    username: merginUsername.value,
                    password: merginPassword.value,
                    project: merginProject.value
                })
            });
            const data = await response.json();

            if (data.success) {
                syncFile.innerHTML = '<option value="">Select a GeoPackage...</option>';
                data.files.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file.path;
                    const sizeKB = Math.round(file.size / 1024);
                    option.textContent = `${file.path} (${sizeKB} KB)`;
                    syncFile.appendChild(option);
                });
                if (data.files.length === 0) {
                    showStatus(gpkgStatus, 'info', 'No GeoPackage files found in this project. Upload a .gpkg file first or choose "From Database" initialization.');
                }
            } else {
                showStatus(gpkgStatus, 'error', data.error);
                syncFile.innerHTML = '<option value="">Error loading files</option>';
            }
        } catch (error) {
            showStatus(gpkgStatus, 'error', 'Network error: ' + error.message);
            syncFile.innerHTML = '<option value="">Error loading files</option>';
        }
    }

    // Update config summary
    function updateConfigSummary() {
        const initFrom = document.querySelector('input[name="init-from"]:checked').value;

        configSummary.innerHTML = `
            <div class="summary-item">
                <span class="summary-label">Mergin URL</span>
                <span class="summary-value">${merginUrl.value}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Username</span>
                <span class="summary-value">${merginUsername.value}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Project</span>
                <span class="summary-value">${merginProject.value}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">GeoPackage</span>
                <span class="summary-value">${syncFile.value || '(will be created)'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Modified Schema</span>
                <span class="summary-value">${schemaModified.value}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Base Schema</span>
                <span class="summary-value">${schemaBase.value}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Initialize From</span>
                <span class="summary-value">${initFrom === 'gpkg' ? 'GeoPackage' : 'Database'}</span>
            </div>
        `;
    }

    // Listen for init-from changes
    document.querySelectorAll('input[name="init-from"]').forEach(radio => {
        radio.addEventListener('change', updateConfigSummary);
    });

    // Save configuration
    saveConfigBtn.addEventListener('click', async function() {
        setLoading(saveConfigBtn, true);
        hideStatus(saveStatus);

        const initFrom = document.querySelector('input[name="init-from"]:checked').value;

        const configData = {
            mergin: {
                url: merginUrl.value,
                username: merginUsername.value,
                password: merginPassword.value
            },
            init_from: initFrom,
            connection: {
                conn_info: pgConnInfo.value,
                modified: schemaModified.value,
                base: schemaBase.value,
                mergin_project: merginProject.value,
                sync_file: syncFile.value
            },
            daemon: {
                sleep_time: 10
            }
        };

        try {
            const response = await fetch('/api/wizard/save-config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(configData)
            });
            const data = await response.json();

            if (data.success) {
                showStatus(saveStatus, 'success', 'Configuration saved successfully! You can now go to the Dashboard to start syncing.');
            } else {
                showStatus(saveStatus, 'error', data.error);
            }
        } catch (error) {
            showStatus(saveStatus, 'error', 'Network error: ' + error.message);
        } finally {
            setLoading(saveConfigBtn, false);
        }
    });

    // Utility functions
    function setLoading(btn, loading) {
        const text = btn.querySelector('.btn-text');
        const spinner = btn.querySelector('.btn-spinner');
        if (loading) {
            text.style.display = 'none';
            spinner.style.display = 'inline-block';
            btn.disabled = true;
        } else {
            text.style.display = 'inline';
            spinner.style.display = 'none';
            btn.disabled = false;
        }
    }

    function showStatus(element, type, message) {
        element.className = 'status-message ' + type;
        element.textContent = message;
        element.style.display = 'block';
    }

    function hideStatus(element) {
        element.style.display = 'none';
        element.className = 'status-message';
    }

    // Load existing config if available
    async function loadExistingConfig() {
        try {
            const response = await fetch('/api/wizard/load-config');
            const data = await response.json();

            if (data.success && data.config && Object.keys(data.config).length > 0) {
                const config = data.config;

                // Populate Mergin fields
                if (config.mergin) {
                    if (config.mergin.url) merginUrl.value = config.mergin.url;
                    if (config.mergin.username) merginUsername.value = config.mergin.username;
                    if (config.mergin.password) merginPassword.value = config.mergin.password;
                }

                // Populate connection fields
                if (config.connections && config.connections.length > 0) {
                    const conn = config.connections[0];
                    if (conn.conn_info) pgConnInfo.value = conn.conn_info;
                    if (conn.modified) schemaModified.value = conn.modified;
                    if (conn.base) schemaBase.value = conn.base;
                }

                // Set init_from
                if (config.init_from) {
                    const radio = document.querySelector(`input[name="init-from"][value="${config.init_from}"]`);
                    if (radio) radio.checked = true;
                }
            }
        } catch (error) {
            console.error('Error loading existing config:', error);
        }
    }

    // Initialize
    loadExistingConfig();
    showStep(1);
});
