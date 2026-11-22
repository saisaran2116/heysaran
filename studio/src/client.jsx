import React from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './app.jsx'
import './style.css'
const root = document.querySelector('#root')
const tree = <BrowserRouter><App /></BrowserRouter>
if (root.hasChildNodes()) hydrateRoot(root, tree)
else createRoot(root).render(tree)
